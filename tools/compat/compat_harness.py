#!/usr/bin/env python3
"""Build engine-style HLSL for DeferredShadowPS from a mod ShadowMaskGen.cfx, for one permutation.

usage: compat_harness.py ENGINE_DUMP.hlsl STOCK_ShadowCommon.cfi MOD_ShadowMaskGen.cfx OUT.hlsl [FLAG=0|1 ...]

ENGINE_DUMP is a shader the game itself sent to the compiler (vkd3d-shader dump from the Deck,
VKD3D_SHADER_DUMP_PATH): its declarations (constant buffers, textures, samplers, input struct) are
copied as they are. The functions come from the mod source with %_RT_ flags set as given
(e.g. SAMPLE2=1 QUALITY=1 SHADOW_JITTERING=1), the way the engine resolves them.
"""
import re, sys

dump, common_path, mod_path, out = sys.argv[1:5]
flags = dict(a.split('=', 1) for a in sys.argv[5:])

d = open(dump).read()
decl = d[:d.index('float GetLinearDepth(')]
samplers = re.findall(r'^sampler2D [A-Za-z0-9_]+;\n', d, re.M)  # declared further down in the dump
fin = re.search(r'struct fragInShadowDeferred\n\{.*?\};\n', d, re.S).group(0)

common = open(common_path, 'rb').read().decode('ascii').replace('\r\n', '\n')
mod = open(mod_path, 'rb').read().decode('ascii').replace('\r\n', '\n')


def func(text, head):
    a = text.index(head)
    b = text.index('{', a)
    depth = 0
    for i in range(b, len(text)):
        depth += {'{': 1, '}': -1}.get(text[i], 0)
        if depth == 0:
            return text[a:i + 1] + '\n'
    raise ValueError(head)


if 'struct pixout_fcs' in mod:  # compat source (1.1+): own helpers, stock sample-count helpers from ShadowCommon.cfi
    h = mod.index('struct pixout_fcs')
    parts = [func(common, 'int GetShadowSamplesNum()'), func(common, 'int GetShadowQuality()'),
             func(common, 'float2 GetKernelSize()'), fin,
             mod[h:mod.index('// FarContactShadows (kcd1-sss): sun screen-space shadows')]]
else:  # release 1.0 source: stock helpers exactly as the engine emitted them (flags already resolved for
    # the dump's permutation, so only permutations with the dump's QUALITY/QUALITY1/JITTERING/MIXED flags are valid)
    parts = [d[d.index('float GetLinearDepth('):d.index('struct fragInShadowDeferred')], fin,
             func(mod, 'half CalcShadow(')]
for head in ('float4 CalcHomogeneousPos(', 'float4 CalcHomogeneousBlendPos(', 'float BlendVP(',
             'float4 CalcShadowSpace(', 'void CalculateFarSSShadow(', '[earlydepthstencil]'):
    parts.append(func(mod, head))
decl += ''.join(x for x in samplers if x not in ''.join(parts))  # 1.0 mode: the dump block declares sRotSampler itself

defines = '''#define LIGHTINGMODEL_STANDARD 0
#define LIGHTINGMODEL_TRANSMITTANCE 1
#define LIGHTINGMODEL_POM_SS 2
#define MAX_FRACTIONAL_8_BIT (255.0f / 256.0f)
#define MIDPOINT_8_BIT (127.0f / 255.0f)
#define TWO_BITS_EXTRACTION_FACTOR (3.0f + MAX_FRACTIONAL_8_BIT)
#define QUALITY_LOW 0
#define QUALITY_MEDIUM 1
#define QUALITY_HIGH 2
#define QUALITY_VERYHIGH 3
'''
names = set(re.findall(r'%_RT_([A-Z0-9_]+)', ''.join(parts)))
defines += ''.join(f'#define RT_{n} {flags.get(n, "0")}\n' for n in sorted(names))
body = re.sub(r'%_RT_', 'RT_', ''.join(parts))
open(out, 'w').write(defines + decl + body)
print('wrote', out, 'flags', {n: flags.get(n, '0') for n in sorted(names)})
