#!/usr/bin/env python3
"""Make the FarContactShadows shader build with every shader compiler the game meets.

usage: make_compat.py MOD_ShadowMaskGen.cfx OUT_DIR [version=V] [ownsurface=1]

On Windows the game compiles shaders with its own Microsoft d3dcompiler_47.dll. Under Proton it gets
Wine's d3dcompiler_47, which uses vkd3d-shader. DeferredShadowPS called stock helpers (Common.cfi,
ShadowCommon.cfi) that vkd3d-shader cannot build: half arithmetic (vkd3d 2.0 = Proton 11.0 aborts),
default arguments (1.8 = Proton 8), out-parameter casts (1.14 = Proton 9). The pixel shader then never
compiles and the game draws no sun shadows.

This gives DeferredShadowPS float-only copies of those helpers (Fcs*), with the same maths, and leaves
the stock helpers alone for the other shaders. On SM5 the Microsoft compiler treats half as float, so
Windows results do not change.

Writes OUT_DIR/src/ShadowMaskGen.cfx (CRLF), OUT_DIR/src/ShadowMaskGen.compat.diff and
OUT_DIR/FarContactShadows/{mod.manifest, Data/FarContactShadows.pak}. Every replacement must match once.
"""
import difflib, os, re, sys, zipfile

src_path, out = sys.argv[1], sys.argv[2]
opts = dict(a.split('=', 1) for a in sys.argv[3:])
version = opts.get('version', '1.0')

raw = open(src_path, 'rb').read().decode('ascii')
s = raw.replace('\r\n', '\n')


def rep(text, old, new):
    assert text.count(old) == 1, ('expected once', old[:80], text.count(old))
    return text.replace(old, new, 1)


HELPERS = r'''//////////////////////////////////////////////////////////////////////////////////////////////////////
// FarContactShadows (kcd1-sss) compat: float-only copies of the stock helpers DeferredShadowPS uses.
// Proton's shader compiler (vkd3d-shader) cannot build the stock ones (half maths, default arguments,
// out-parameter casts). Same maths as stock GetLinearDepth, DecodeLightingModel, DecodeSunSelfShadowing,
// shadow_sample, DoubleSampleRotated, irregular_filter(_impl) and CalcShadow.

struct pixout_fcs
{
	float4 Color : COLOR0;
};

float FcsSceneDepth(float2 ScreenTC)
{
	return sceneDepthTexture.Load(int3(ScreenTC * PS_ScreenSize.xy, 0)).x;
}

int FcsLightingModel(float4 bufferA)
{
	return (int)floor(bufferA.w * TWO_BITS_EXTRACTION_FACTOR);
}

float FcsSunSelfShadowing(int lightingModel, float4 bufferC)
{
	return (lightingModel == LIGHTINGMODEL_POM_SS) ? saturate(bufferC.z / MIDPOINT_8_BIT - 1) : 0;
}

float FcsShadowTap(float2 tc, float fDepth)
{
	return depthMapSampler0.SampleCmpLevelZero(SAMPLER_STATE_depthMapSampler, tc, fDepth);
}

float FcsShadowDepth(float2 tc)
{
	return depthMapSampler0.SampleLevel(SAMPLER_STATE_depthMapSamplerLinear, tc, 0.0f).x;
}

float4 FcsShadowTaps4(float4 P0, float4 rotMatr, float4 kernel0, float4 kernel1)
{
	const float4 fetch0 = P0.xyxy + rotMatr.xyzw * kernel0.xxww + rotMatr.zwxy * kernel0.yyzz;
	const float4 fetch1 = P0.xyxy + rotMatr.xyzw * kernel1.xxww + rotMatr.zwxy * kernel1.yyzz;
	return float4(FcsShadowTap(fetch0.xy, P0.z), FcsShadowTap(fetch0.zw, P0.z),
	              FcsShadowTap(fetch1.xy, P0.z), FcsShadowTap(fetch1.zw, P0.z));
}

// Contact hardening: occluder depth and coverage of four taps (x = area, y = coverage).
float2 FcsHardenTaps4(float4 P0, float4 kernel0, float4 kernel1, float2 kernelScale)
{
	const float4 sampleDepth = float4(FcsShadowDepth(P0.xy + kernel0.xy * kernelScale), FcsShadowDepth(P0.xy + kernel0.zw * kernelScale),
	                                  FcsShadowDepth(P0.xy + kernel1.xy * kernelScale), FcsShadowDepth(P0.xy + kernel1.zw * kernelScale));
	const float4 localArea = P0.zzzz - sampleDepth;
	const float4 samplNum = 1.0f - step(localArea, 0.0f);
	return float2(dot(min(abs(localArea), vAdaption.xxxx), samplNum), dot(samplNum, float4(1, 1, 1, 1)));
}

// Stock kernel sizes (GetShadowSamplesNum): low 4 taps, medium 8, high and very high 16. Written out
// without loops: Proton 9-10 compilers crash or hang on the stock loop.
float FcsCalcShadow(float4 vShPos, float2 vNoisePos, const bool bContactHardening)
{
	float4 P0 = vShPos;
#if %_RT_SHADOW_MIXED_MAP_G16R16
	P0.z = clamp(P0.z, 0.0f, 0.999999f);
#endif
#if %_RT_SHADOW_JITTERING
	const float2 vKernelSize = GetKernelSize();
	const float2 randDirTC = vNoisePos.xy * (vKernelSize.y * 15.0f);
	const float2 kernelRadius = vKernelSize * vInvShadowMapSize.xx;
	const float2 rotSample = tex2D(sRotSampler, randDirTC.xy).xy * kernelRadius.xy;
	float4 rotMatr = float4(rotSample.x, -rotSample.y, rotSample.y, rotSample.x);

	// Depth range estimation (contact hardening)
	if (bContactHardening)
	{
		const float2 kernelScale = kernelRadius * 2.7f;
		float2 vAcc = float2(0.0f, 0.01f) + FcsHardenTaps4(P0, irreg_kernel_2d[0], irreg_kernel_2d[1], kernelScale);
	#if %_RT_QUALITY || %_RT_QUALITY1
		vAcc += FcsHardenTaps4(P0, irreg_kernel_2d[2], irreg_kernel_2d[3], kernelScale);
	#endif
	#if %_RT_QUALITY1
		vAcc += FcsHardenTaps4(P0, irreg_kernel_2d[4], irreg_kernel_2d[5], kernelScale);
		vAcc += FcsHardenTaps4(P0, irreg_kernel_2d[6], irreg_kernel_2d[7], kernelScale);
	#endif
		if (vAcc.y > 0.1f)
			rotMatr *= max(vAcc.x / vAcc.y * vAdaption.y, vAdaption.z);
		else
			rotMatr *= vAdaption.z;
	}

	float4 vTaps = FcsShadowTaps4(P0, rotMatr, irreg_kernel_2d[0], irreg_kernel_2d[1]);
	#if %_RT_QUALITY || %_RT_QUALITY1
	vTaps += FcsShadowTaps4(P0, rotMatr, irreg_kernel_2d[2], irreg_kernel_2d[3]);
	#endif
	#if %_RT_QUALITY1
	vTaps += FcsShadowTaps4(P0, rotMatr, irreg_kernel_2d[4], irreg_kernel_2d[5]);
	vTaps += FcsShadowTaps4(P0, rotMatr, irreg_kernel_2d[6], irreg_kernel_2d[7]);
	#endif
	const float fShadow = dot(vTaps, float4(1, 1, 1, 1)) / GetShadowSamplesNum();
	return fShadow * fShadow;
#else
	return FcsShadowTap(P0.xy, P0.z);
#endif
}

'''
ANCHOR = '// FarContactShadows (kcd1-sss): sun screen-space shadows that reach as far as the sun shadow cascades.\n'
s = rep(s, ANCHOR, HELPERS + ANCHOR)

# CalculateFarSSShadow (mod function): own helpers. GetLinearDepth(float) returns its argument unchanged.
s = rep(s, '\t\tfloat fScrDepth = GetLinearDepth( sceneDepthTexture, vTC.xy ) * PS_NearFarClipDist.y;',
           '\t\tfloat fScrDepth = FcsSceneDepth(vTC.xy) * PS_NearFarClipDist.y;')
s = rep(s, '\t\tfloat fRayDepth = GetLinearDepth(g_PS_ProjRatio.y / (vTC.z - g_PS_ProjRatio.x)) * PS_NearFarClipDist.y;',
           '\t\tfloat fRayDepth = (g_PS_ProjRatio.y / (vTC.z - g_PS_ProjRatio.x)) * PS_NearFarClipDist.y;')
s = rep(s, 'const bool bFcsFol = (DecodeLightingModel(sceneGBufferA[vFcsPix]) == LIGHTINGMODEL_TRANSMITTANCE)',
           'const bool bFcsFol = (FcsLightingModel(sceneGBufferA[vFcsPix]) == LIGHTINGMODEL_TRANSMITTANCE)')

# DeferredShadowPS
a = s.index('pixout_cl DeferredShadowPS(fragInShadowDeferred IN)')
b = s.index('pixout_cl CloudsShadowPS(fragInShadowDeferred IN)')
ps = s[a:b]
for old, new in (
        ('pixout_cl DeferredShadowPS(fragInShadowDeferred IN)\n{\n  pixout_cl OUT;',
         'pixout_fcs DeferredShadowPS(fragInShadowDeferred IN)\n{\n  pixout_fcs OUT;'),
        ('GetLinearDepth( sceneDepthTexture, IN.ScreenTC.xy )', 'FcsSceneDepth(IN.ScreenTC.xy)'),
        ('  half fInShadow = CalcShadow(P0, NoiseP, bContactHardening);',
         '  float fInShadow = FcsCalcShadow(P0, NoiseP, bContactHardening);'),
        ('\thalf2 fDist = 2.0*abs(P0.xy-half2(0.5,0.5));', '\tfloat2 fDist = 2.0*abs(P0.xy-float2(0.5,0.5));'),
        ('  half fFadeF = ', '  float fFadeF = '),
        ('int lightingModelSSS = DecodeLightingModel(sceneGBufferA[pixelCoord]);',
         'int lightingModelSSS = FcsLightingModel(sceneGBufferA[pixelCoord]);'),
        ('OUT.Color = 1 - fInShadow * (1 - DecodeSunSelfShadowing(lightingModel, sceneGBufferC[pixelCoord]));',
         'OUT.Color = 1 - fInShadow * (1 - FcsSunSelfShadowing(lightingModel, sceneGBufferC[pixelCoord]));'),
        ('OUT.Color = 1 - fInShadow * (1 - DecodeSunSelfShadowing(sceneGBufferA[pixelCoord], sceneGBufferB[pixelCoord], sceneGBufferC[pixelCoord]));',
         'OUT.Color = 1 - fInShadow * (1 - FcsSunSelfShadowing(lightingModelSSS, sceneGBufferC[pixelCoord]));')):
    ps = rep(ps, old, new)
for word in ('half', 'GetLinearDepth', 'Decode', 'CalcShadow('):
    assert word not in ps.replace('FcsCalcShadow(', ''), ('left in DeferredShadowPS:', word)
s = s[:a] + ps + s[b:]

# ownsurface=1 (1.0.1): a surface cannot shadow itself. Rays that point into the screen (facing a low sun) move
# less than a pixel per step, so the first samples read the receiver's own pixel, or neighbours at the same depth
# on flat ground, as blockers: a dark square around the sun about 400 px wide (half the Deck's screen, a small
# patch at 4K) and dark bands on flat ground under a low side sun. 1/depth of a plane is linear across the
# screen, so the receiver's plane comes from its four nearest depths (the flatter side of each pair, so edges
# don't count); samples within 0.5 % plus about one pixel's depth change of that plane are skipped.
OWN_HELPER = """
float FcsSceneDepthPix(int2 vPix)
{
	return sceneDepthTexture.Load(int3(clamp(vPix, int2(0, 0), int2(PS_ScreenSize.xy) - int2(1, 1)), 0)).x;
}

int FcsLightingModel(float4 bufferA)
"""
OWN_PLANE = """	// A surface cannot shadow itself: skip samples that lie on the receiver's plane (1/depth is linear across
	// the screen for a plane; the flatter neighbour of each pair is used so edges don't count).
	const float fFcsIz0 = 1.0 / max(fDepth0, 1e-6);
	const float fFcsIzR = 1.0 / max(FcsSceneDepthPix(vFcsPix0 + int2(1, 0)), 1e-6) - fFcsIz0;
	const float fFcsIzL = fFcsIz0 - 1.0 / max(FcsSceneDepthPix(vFcsPix0 - int2(1, 0)), 1e-6);
	const float fFcsIzD = 1.0 / max(FcsSceneDepthPix(vFcsPix0 + int2(0, 1)), 1e-6) - fFcsIz0;
	const float fFcsIzU = fFcsIz0 - 1.0 / max(FcsSceneDepthPix(vFcsPix0 - int2(0, 1)), 1e-6);
	const float fFcsGx = (abs(fFcsIzR) < abs(fFcsIzL)) ? fFcsIzR : fFcsIzL;
	const float fFcsGy = (abs(fFcsIzD) < abs(fFcsIzU)) ? fFcsIzD : fFcsIzU;
	// Same-surface tolerance: 0.5 % of depth plus the depth change of about one pixel.
	const float fFcsPlaneTolRel = 0.005;
	const float fFcsPlaneTolPix = abs(fFcsGx) + abs(fFcsGy);

	float fFcsOccMax = 0;
"""
OWN_LOOP = """		const float fFcsIzPlane = fFcsIz0 + fFcsGx * (float)(vFcsPix.x - vFcsPix0.x) + fFcsGy * (float)(vFcsPix.y - vFcsPix0.y);
		const float fFcsIzScr = PS_NearFarClipDist.y / max(fScrDepth, 1e-6);
		fFcsOcc *= saturate(abs(fFcsIzScr - fFcsIzPlane) / max(fFcsPlaneTolRel * abs(fFcsIzPlane) + fFcsPlaneTolPix, 1e-6) - 1);
		fFcsOccMax = max(fFcsOccMax, fFcsOcc);
"""
if opts.get('ownsurface') == '1':
    s = rep(s, '\nint FcsLightingModel(float4 bufferA)\n', OWN_HELPER)
    s = rep(s, 'const float4x4 matComposite, inout float fInShadow, const bool bFcsRecvFol)',
               'const float4x4 matComposite, inout float fInShadow, const bool bFcsRecvFol, const int2 vFcsPix0)')
    s = rep(s, '\tfloat fFcsOccMax = 0;\n', OWN_PLANE)
    s = rep(s, '\t\tfFcsOccMax = max(fFcsOccMax, fFcsOcc);\n', OWN_LOOP)
    s = rep(s, '\t\tCalculateFarSSShadow( SceneDepth, WorldP, WorldP + g_PS_SunLightDir.xyz, CompMatrix, fInShadow, bFcsRecvFol );',
               '\t\tconst int2 vFcsPix0 = int2(IN.ScreenTC.xy * PS_ScreenSize.xy);\n'
               '\t\tCalculateFarSSShadow( SceneDepth, WorldP, WorldP + g_PS_SunLightDir.xyz, CompMatrix, fInShadow, bFcsRecvFol, vFcsPix0 );')

os.makedirs(f'{out}/src', exist_ok=True)
mod_src = s.replace('\n', '\r\n').encode('ascii')
open(f'{out}/src/ShadowMaskGen.cfx', 'wb').write(mod_src)
open(f'{out}/src/ShadowMaskGen.compat.diff', 'w').writelines(difflib.unified_diff(
    raw.replace('\r\n', '\n').splitlines(True), s.splitlines(True), 'release-1.0/ShadowMaskGen.cfx', 'compat/ShadowMaskGen.cfx'))

mod = f'{out}/FarContactShadows'
os.makedirs(f'{mod}/Data', exist_ok=True)
# Release manifest (src/mod.manifest: name, author, description), with the version set.
manifest = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mod.manifest'),
                'rb').read().decode('ascii').replace('\r\n', '\n')
manifest, n = re.subn(r'<version>[^<]*</version>', f'<version>{version}</version>', manifest)
assert n == 1, 'mod.manifest needs exactly one <version> line'
open(f'{mod}/mod.manifest', 'w', newline='\r\n').write(manifest)
with zipfile.ZipFile(f'{mod}/Data/FarContactShadows.pak', 'w', zipfile.ZIP_DEFLATED) as z:
    zi = zipfile.ZipInfo('Shaders/HWScripts/CryFX/ShadowMaskGen.cfx', (2026, 11, 4, 0, 0, 0))  # fixed time: same pak sha every build
    zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, mod_src)
print('wrote', f'{out}/src/ShadowMaskGen.cfx', f'{mod}/Data/FarContactShadows.pak', len(mod_src), 'bytes source')
