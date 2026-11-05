#!/usr/bin/env python3
"""Build the FarContactShadows KCD1 mod from the stock ShadowMaskGen.cfx.

usage: make_sss_mod.py STOCK_ShadowMaskGen.cfx OUT_DIR [CACHE_STUB_DIR] [debug] [len=F steps=N thick=F bias=F foliage=1 thin=1 foliagecast=0 grass=1 folscale=F folstrength=F fol=T:S[,T:S,T:S] folsplit=TG:SG,TF:SF abtree=1 abright=T:S gbdebug=1 nosharpen=1 lookup=FILE stamp=TEXT version=V]

Writes OUT_DIR/src/ShadowMaskGen.cfx (patched, CRLF kept), OUT_DIR/src/ShadowMaskGen.diff,
and the installable mod folder OUT_DIR/FarContactShadows/{mod.manifest, Data/FarContactShadows.pak}.
Every replacement must match the stock text exactly once, or the script stops.
"""
import sys, os, zipfile, difflib

stock_path, out = sys.argv[1], sys.argv[2]
# Optional: folder with header-only shader caches (cgpshaders/, cgvshaders/) written by the game for this exact source.
# Packed over Engine/shadercache.pak so the stock precompiled DeferredShadow shaders cannot be used.
stub_dir = sys.argv[3] if len(sys.argv) > 3 else None
# Further arguments: 'debug' paints dark rings at 8-10, 30-33 and 100-105 m wherever the mod code runs;
# NAME=VALUE overrides a tunable (len, steps, thick, bias) or sets the manifest version (version=0.5).
extra = sys.argv[4:]
debug = 'debug' in extra
opts = dict(a.split('=', 1) for a in extra if '=' in a)
raw = open(stock_path, 'rb').read()
assert b'\r\n' in raw
s = raw.decode('ascii').replace('\r\n', '\n')

FUNC = r'''
//////////////////////////////////////////////////////////////////////////////////////////////////////
// FarContactShadows (kcd1-sss): sun screen-space shadows that reach as far as the sun shadow cascades.
// Ray length scales with view depth and there is no 2-3 m fade (after Crysis Remastered SSS).
// Near the camera it matches the stock ray (3.4 cm, 1 cm bias, 3 cm occluder thickness).
void CalculateFarSSShadow(const float fDepth0, const float3 vPosWS, const float3 vPosLight, const float4x4 matComposite, inout float fInShadow)
{
	// Tunables. Crysis Remastered values are given in brackets.
	// Ray length as a fraction of view depth (0.02), never shorter than the stock 3.4 cm ray.
	const float fFcsLenScale = 0.02;
	const float fFcsLenMin = 0.034;
	// Ray steps (12), stock 16.
	const int nFcsSteps = 16;
	// Depth bias relative to ray depth (0.002 to 0.003), at least the stock 1 cm.
	const float fFcsBiasRel = 0.002;
	const float fFcsBiasMin = 0.01;
	// Occluder thickness 1.5 cm plus this fraction of depth (0.02), at least the stock 3 cm.
	const float fFcsThickRel = 0.02;
	const float fFcsThickMin = 0.03;
	// Depth test ramp of 5 mm (stock and Crysis).
	const float fFcsHardness = 200;
	// Far fade in metres, well past the last sun cascade.
	const float fFcsFadeStart = 1000;
	const float fFcsFadeEnd = 1200;

	const float fFcsViewDist = fDepth0 * PS_NearFarClipDist.y;
	const float fFcsRayLen = max(fFcsLenMin, fFcsViewDist * fFcsLenScale);

	float4 vTC0 = mul(matComposite, float4(vPosWS, 1));
	float4 vTC1 = mul(matComposite, float4(vPosWS + normalize(vPosLight - vPosWS) * fFcsRayLen, 1));

	// Shorten rays that project long on screen (Crysis shadowLengthScaleSS).
	float fFcsScaleSS = length(vTC1.xyz - vTC0.xyz) / fFcsRayLen;
	fFcsScaleSS = 1.0 / max(1.0, 0.3 + 0.7 * fFcsScaleSS);

	float4 vFcsStep = (vTC1 - vTC0) * (fFcsScaleSS / nFcsSteps);
	vTC0 += vFcsStep;

	float fFcsOccMax = 0;

	[loop] for (int s = 0; s < nFcsSteps; s++)
	{
		float4 vTC = vTC0 / vTC0.w;
		vTC.xy = vTC.xy * 0.5f + 0.5f;
		vTC.y = 1 - vTC.y;

		if (vTC.x < 0 || vTC.x > 1 || vTC.y < 0 || vTC.y > 1)
			break;

		float fScrDepth = GetLinearDepth( sceneDepthTexture, vTC.xy ) * PS_NearFarClipDist.y;
		float fRayDepth = GetLinearDepth(g_PS_ProjRatio.y / (vTC.z - g_PS_ProjRatio.x)) * PS_NearFarClipDist.y;
		fRayDepth -= max(fFcsBiasMin, fRayDepth * fFcsBiasRel);

		float fFcsThick = max(fFcsThickMin, 0.015 + fRayDepth * fFcsThickRel) * fFcsScaleSS;
		float fFcsOcc = saturate((fRayDepth - fScrDepth) * fFcsHardness) * saturate((fScrDepth + fFcsThick - fRayDepth) * fFcsHardness);
		fFcsOccMax = max(fFcsOccMax, fFcsOcc);

		vTC0 += vFcsStep;
	}

	float fInSSS = 1 - fFcsOccMax;
	fInSSS = lerp(fInSSS, 1, saturate((fFcsViewDist - fFcsFadeStart) / (fFcsFadeEnd - fFcsFadeStart)));

	fInShadow = min(fInSSS, fInShadow);
}

'''

TUNABLES = {'len': 'const float fFcsLenScale = 0.02;', 'steps': 'const int nFcsSteps = 16;',
            'thick': 'const float fFcsThickRel = 0.02;', 'bias': 'const float fFcsBiasRel = 0.002;'}
for key, line in TUNABLES.items():
    if key in opts:
        assert FUNC.count(line) == 1, line
        FUNC = FUNC.replace(line, line.rsplit('=', 1)[0] + '= ' + opts[key] + ';')
# thin=1: foliage blockers (translucent pixels without a skin profile) count as thin, so grass blades cast
# blade-shaped shadows instead of solid columns (each blade was treated as 4% of its distance deep).
THIN_OLD = '''\t\tfloat fFcsThick = max(fFcsThickMin, 0.015 + fRayDepth * fFcsThickRel) * fFcsScaleSS;
'''
THIN_NEW = '''\t\tfloat fFcsThick = max(fFcsThickMin, 0.015 + fRayDepth * fFcsThickRel) * fFcsScaleSS;
\t\t// Foliage blockers are thin: about two ray steps, at least 2 cm.
\t\tint2 vFcsPix = int2(vTC.xy * PS_ScreenSize.xy);
\t\t[branch] if ((DecodeLightingModel(sceneGBufferA[vFcsPix]) == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[vFcsPix].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0))
\t\t\tfFcsThick = max(fFcsThinMin, fFcsStepLen * 2);
'''
STEP_OLD = '''\tfloat4 vFcsStep = (vTC1 - vTC0) * (fFcsScaleSS / nFcsSteps);
'''
STEP_NEW = '''\tfloat4 vFcsStep = (vTC1 - vTC0) * (fFcsScaleSS / nFcsSteps);
\tconst float fFcsThinMin = 0.02;
\tconst float fFcsStepLen = fFcsRayLen * fFcsScaleSS / nFcsSteps;
'''
if opts.get('thin') == '1':
    for o, n in ((THIN_OLD, THIN_NEW), (STEP_OLD, STEP_NEW)):
        assert FUNC.count(o) == 1, o
        FUNC = FUNC.replace(o, n)
# foliagecast=0: foliage blockers (translucent pixels without a skin profile) cast no contact shadows at all;
# foliage still receives them from everything else (rocks, carts, people).
NOCAST_OLD = '''\t\tfloat fFcsOcc = saturate((fRayDepth - fScrDepth) * fFcsHardness) * saturate((fScrDepth + fFcsThick - fRayDepth) * fFcsHardness);
'''
NOCAST_NEW = NOCAST_OLD + '''\t\t// Foliage does not cast (it still receives).
\t\tint2 vFcsPixC = int2(vTC.xy * PS_ScreenSize.xy);
\t\t[branch] if ((DecodeLightingModel(sceneGBufferA[vFcsPixC]) == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[vFcsPixC].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0))
\t\t\tfFcsOcc = 0;
'''
if opts.get('foliagecast') == '0':
    assert FUNC.count(NOCAST_OLD) == 1
    FUNC = FUNC.replace(NOCAST_OLD, NOCAST_NEW)
# grass=1 (needs thin=1): foliage shadows are also short and soft. A foliage blocker only counts within the first
# folscale of the ray (default 0.33), fades out along it, and darkens at most folstrength (default 0.75).
GRASS_OLD = '''\t\tint2 vFcsPix = int2(vTC.xy * PS_ScreenSize.xy);
\t\t[branch] if ((DecodeLightingModel(sceneGBufferA[vFcsPix]) == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[vFcsPix].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0))
\t\t\tfFcsThick = max(fFcsThinMin, fFcsStepLen * 2);
\t\tfloat fFcsOcc = saturate((fRayDepth - fScrDepth) * fFcsHardness) * saturate((fScrDepth + fFcsThick - fRayDepth) * fFcsHardness);
'''
GRASS_NEW = '''\t\tint2 vFcsPix = int2(vTC.xy * PS_ScreenSize.xy);
\t\tconst bool bFcsFol = (DecodeLightingModel(sceneGBufferA[vFcsPix]) == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[vFcsPix].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0);
\t\tif (bFcsFol)
\t\t\tfFcsThick = max(fFcsThinMin, fFcsStepLen * 2);
\t\tfloat fFcsOcc = saturate((fRayDepth - fScrDepth) * fFcsHardness) * saturate((fScrDepth + fFcsThick - fRayDepth) * fFcsHardness);
\t\t// Foliage shadows are short and soft: they fade out over the first part of the ray.
\t\tif (bFcsFol)
\t\t\tfFcsOcc *= fFcsFolStrength * saturate(1 - (s + 1) / (nFcsSteps * fFcsFolScale));
'''
GRASS_CONST_OLD = '''\tconst float fFcsThinMin = 0.02;
'''
if opts.get('grass') == '1':
    assert opts.get('thin') == '1', 'grass=1 needs thin=1'
    assert FUNC.count(GRASS_OLD) == 1 and FUNC.count(GRASS_CONST_OLD) == 1
    FUNC = FUNC.replace(GRASS_OLD, GRASS_NEW)
    FUNC = FUNC.replace(GRASS_CONST_OLD, GRASS_CONST_OLD + '\tconst float fFcsFolScale = ' + opts.get('folscale', '0.33') +
                        ';\n\tconst float fFcsFolStrength = ' + opts.get('folstrength', '0.75') + ';\n')
# fol=T:S (needs thin=1): foliage blockers use T x the normal thickness and darken by S (0..1).
# fol=T:S,T:S,T:S is a comparison build: left, middle and right thirds of the screen each get one pair,
# with dark lines at the band edges.
FOL_OLD = '''\t\tint2 vFcsPix = int2(vTC.xy * PS_ScreenSize.xy);
\t\t[branch] if ((DecodeLightingModel(sceneGBufferA[vFcsPix]) == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[vFcsPix].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0))
\t\t\tfFcsThick = max(fFcsThinMin, fFcsStepLen * 2);
\t\tfloat fFcsOcc = saturate((fRayDepth - fScrDepth) * fFcsHardness) * saturate((fScrDepth + fFcsThick - fRayDepth) * fFcsHardness);
'''
fol_bands = False
# folsplit=TG:SG,TF:SF: foliage blockers use TG:SG when the shadow falls on a non-foliage surface (ground, rock, wood)
# and TF:SF when it falls on foliage (leaves on leaves, grass on grass).
fol_split = 'folsplit' in opts
if 'fol' in opts or fol_split:
    assert opts.get('thin') == '1' and opts.get('grass') != '1', 'fol= / folsplit= need thin=1 and no grass=1'
    assert not ('fol' in opts and fol_split), 'use fol= or folsplit=, not both'
    pairs = [tuple(x.split(':')) for x in opts['folsplit' if fol_split else 'fol'].split(',')]
    assert (len(pairs) == 2 if fol_split else len(pairs) in (1, 3)) and all(len(x) == 2 for x in pairs)
    if fol_split:
        (tg, sg), (tf, sf) = pairs
        t_expr = f'(bFcsRecvFol ? {tf} : {tg})'
        s_expr = f'(bFcsRecvFol ? {sf} : {sg})'
        if 'abright' in opts:
            # A/B test: right half of the screen uses one setting for every foliage blocker.
            tr, sr = opts['abright'].split(':')
            t_expr = f'((vTC.x >= 0.5) ? {tr} : {t_expr})'
            s_expr = f'((vTC.x >= 0.5) ? {sr} : {s_expr})'
        FUNC_SIG = 'const float4x4 matComposite, inout float fInShadow)'
        assert FUNC.count(FUNC_SIG) == 1
        FUNC = FUNC.replace(FUNC_SIG, 'const float4x4 matComposite, inout float fInShadow, const bool bFcsRecvFol)')
    elif len(pairs) == 1:
        t_expr, s_expr = pairs[0]
    else:
        fol_bands = True
        (ta, sa), (tb, sb), (tc, sc) = pairs
        t_expr = f'((vTC.x < 0.3333) ? {ta} : ((vTC.x < 0.6667) ? {tb} : {tc}))'
        s_expr = f'((vTC.x < 0.3333) ? {sa} : ((vTC.x < 0.6667) ? {sb} : {sc}))'
    FOL_NEW = f'''\t\tint2 vFcsPix = int2(vTC.xy * PS_ScreenSize.xy);
\t\tconst bool bFcsFol = (DecodeLightingModel(sceneGBufferA[vFcsPix]) == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[vFcsPix].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0);
\t\t// Foliage blockers: thickness factor and shadow strength.
\t\tconst float fFcsFolThick = {t_expr};
\t\tconst float fFcsFolStrength = {s_expr};
\t\tif (bFcsFol)
\t\t\tfFcsThick *= fFcsFolThick;
\t\tfloat fFcsOcc = saturate((fRayDepth - fScrDepth) * fFcsHardness) * saturate((fScrDepth + fFcsThick - fRayDepth) * fFcsHardness);
\t\tif (bFcsFol)
\t\t\tfFcsOcc *= fFcsFolStrength;
'''
    assert FUNC.count(FOL_OLD) == 1
    FUNC = FUNC.replace(FOL_OLD, FOL_NEW)
BAND_LINES = '''
\t// FarContactShadows COMPARISON build: dark lines at 1/3 and 2/3 of the screen width (foliage setting bands).
\tif ((abs(IN.ScreenTC.x - 0.3333) < 0.001) || (abs(IN.ScreenTC.x - 0.6667) < 0.001))
\t\tfInShadow = 0;
'''
GB_DEBUG = '''
\t// FarContactShadows GBUFFER DEBUG build. Foliage pixels (translucent, no skin profile) show one GBuffer value V as
\t// horizontal stripes: in every 32-row period, the top round(V * 32) rows are sunlit and the rest are shadowed.
\t// Screen quarters, left to right: transmittance luma, transmittance Cb (x4 around grey), smoothness, normal up.
\t// Dark vertical lines mark the quarter edges.
\tif ((lightingModelSSS == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[pixelCoord].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0))
\t{
\t\tconst float4 vFcsGA = sceneGBufferA[pixelCoord];
\t\tconst float4 vFcsGC = sceneGBufferC[pixelCoord];
\t\tfloat fFcsV;
\t\tif (IN.ScreenTC.x < 0.25)
\t\t\tfFcsV = frac(vFcsGA.w * TWO_BITS_EXTRACTION_FACTOR);
\t\telse if (IN.ScreenTC.x < 0.5)
\t\t\tfFcsV = saturate(0.5 + (vFcsGC.z - MIDPOINT_8_BIT) * 4);
\t\telse if (IN.ScreenTC.x < 0.75)
\t\t\tfFcsV = vFcsGC.x;
\t\telse
\t\t\tfFcsV = normalize(vFcsGA.xyz * 2 - 1).z * 0.5 + 0.5;
\t\tfInShadow = ((pixelCoord.y & 31) < (uint)round(fFcsV * 32)) ? 1 : 0;
\t}
\tif ((abs(IN.ScreenTC.x - 0.25) < 0.001) || (abs(IN.ScreenTC.x - 0.5) < 0.001) || (abs(IN.ScreenTC.x - 0.75) < 0.001))
\t\tfInShadow = 0;
'''
version = opts.get('version', '0.4') + ('-debug' if debug else '')

ANCHOR = '///////////////// shadows pixel shader //////////////////\n'

OLD_BLOCK = '''\tuint2 pixelCoord = int2(IN.ScreenTC.xy * PS_ScreenSize.xy);
#if %_RT_SAMPLE2
\t
\tint lightingModel = DecodeLightingModel(sceneGBufferA[pixelCoord]);

\t// WH[Woody]: prevent screen-space shadows on translucent geometry (e.g. tents, grass etc.) as it looks ugly/triangled. The only exception are characters with 3PL
\t[branch] if ((lightingModel != LIGHTINGMODEL_TRANSMITTANCE) || ((sceneGBufferB[pixelCoord].w * TWO_BITS_EXTRACTION_FACTOR) >= 1.0))
\t{
\t\t// Apply sun SS shadows
\t\tfloat3 WorldP = g_vViewPos.xyz + IN.WS_ViewVect * SceneDepth;
\t\tCalculateDetailSSShadow( SceneDepth, WorldP, WorldP + g_PS_SunLightDir.xyz, CompMatrix, fInShadow, true );
\t}

\t// Apply POM self-shadowing
\tOUT.Color = 1 - fInShadow * (1 - DecodeSunSelfShadowing(lightingModel, sceneGBufferC[pixelCoord]));
#else
'''

NEW_BLOCK = '''\tuint2 pixelCoord = int2(IN.ScreenTC.xy * PS_ScreenSize.xy);

\t// FarContactShadows: sun SS shadows in EVERY cascade pass. Stock KCD only ran them in cascade 0 (the SAMPLE2
\t// flag, set by C++ only for nShadowMapLod == 0), which with the stock 2-3 m fade capped them at ~3 m.
\tint lightingModelSSS = DecodeLightingModel(sceneGBufferA[pixelCoord]);

\t// WH[Woody]: prevent screen-space shadows on translucent geometry (e.g. tents, grass etc.) as it looks ugly/triangled. The only exception are characters with 3PL
\t[branch] if ((lightingModelSSS != LIGHTINGMODEL_TRANSMITTANCE) || ((sceneGBufferB[pixelCoord].w * TWO_BITS_EXTRACTION_FACTOR) >= 1.0))
\t{
\t\t// Apply sun SS shadows
\t\tfloat3 WorldP = g_vViewPos.xyz + IN.WS_ViewVect * SceneDepth;
\t\tCalculateFarSSShadow( SceneDepth, WorldP, WorldP + g_PS_SunLightDir.xyz, CompMatrix, fInShadow );
\t}

#if %_RT_SAMPLE2
\tint lightingModel = lightingModelSSS;

\t// Apply POM self-shadowing
\tOUT.Color = 1 - fInShadow * (1 - DecodeSunSelfShadowing(lightingModel, sceneGBufferC[pixelCoord]));
#else
'''

# WS_ViewVect was only interpolated for %_RT_SAMPLE2 (cascade 0); every cascade pass needs it now.
OLD_STRUCT = '\tfloat4 ScreenTC\t\t:\tTEXCOORD1;\n#if %_RT_SAMPLE2\n\tfloat3 WS_ViewVect\t:\tTEXCOORD4;\n#endif\n};\n'
NEW_STRUCT = '\tfloat4 ScreenTC\t\t:\tTEXCOORD1;\n\tfloat3 WS_ViewVect\t:\tTEXCOORD4; // FarContactShadows: all permutations\n};\n'
OLD_VS = '#if %_RT_SAMPLE2\n\tOUT.WS_ViewVect = IN.viewDir.xyz;\n#endif\n'
NEW_VS = '\tOUT.WS_ViewVect = IN.viewDir.xyz; // FarContactShadows: all permutations\n'

# foliage=1: grass, leaves and other translucent surfaces receive contact shadows too (stock KCD excluded them).
FOLIAGE_OLD = '''\t// WH[Woody]: prevent screen-space shadows on translucent geometry (e.g. tents, grass etc.) as it looks ugly/triangled. The only exception are characters with 3PL
\t[branch] if ((lightingModelSSS != LIGHTINGMODEL_TRANSMITTANCE) || ((sceneGBufferB[pixelCoord].w * TWO_BITS_EXTRACTION_FACTOR) >= 1.0))
'''
FOLIAGE_NEW = '''\t// FarContactShadows foliage=1: no translucency exclusion, so grass, leaves and tents receive sun SS shadows too.
\t// Stock (WH[Woody]) skipped translucent geometry unless it had a scattering profile (characters with 3PL).
\tif (true)
'''
if opts.get('foliage') == '1':
    assert NEW_BLOCK.count(FOLIAGE_OLD) == 1
    NEW_BLOCK = NEW_BLOCK.replace(FOLIAGE_OLD, FOLIAGE_NEW)

DEBUG_RINGS = '''
\t// FarContactShadows DEBUG build: dark rings at 8-10 m, 30-33 m and 100-105 m wherever this code runs.
\tconst float fFcsDbgDist = SceneDepth * PS_NearFarClipDist.y;
\tif ((fFcsDbgDist > 8 && fFcsDbgDist < 10) || (fFcsDbgDist > 30 && fFcsDbgDist < 33) || (fFcsDbgDist > 100 && fFcsDbgDist < 105))
\t\tfInShadow = 0;
'''
if debug:
    anchor = "\t}\n\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;"
    assert NEW_BLOCK.count(anchor) == 1
    NEW_BLOCK = NEW_BLOCK.replace(anchor, "\t}\n" + DEBUG_RINGS + "\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;")
if fol_bands:
    anchor = "\t}\n\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;"
    assert NEW_BLOCK.count(anchor) == 1
    NEW_BLOCK = NEW_BLOCK.replace(anchor, "\t}\n" + BAND_LINES + "\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;")

if fol_split:
    call = '\t\tCalculateFarSSShadow( SceneDepth, WorldP, WorldP + g_PS_SunLightDir.xyz, CompMatrix, fInShadow );'
    assert NEW_BLOCK.count(call) == 1
    NEW_BLOCK = NEW_BLOCK.replace(call, '''\t\t// FarContactShadows folsplit: is the shadow falling on foliage (translucent, no skin profile)?
\t\tconst bool bFcsRecvFol = (lightingModelSSS == LIGHTINGMODEL_TRANSMITTANCE) && ((sceneGBufferB[pixelCoord].w * TWO_BITS_EXTRACTION_FACTOR) < 1.0);
\t\tCalculateFarSSShadow( SceneDepth, WorldP, WorldP + g_PS_SunLightDir.xyz, CompMatrix, fInShadow, bFcsRecvFol );''')
if opts.get('abtree') == '1':
    # A/B test: left of the screen centre, foliage surfaces get no contact shadows (stock behaviour); right = mod.
    assert fol_split, 'abtree=1 needs folsplit='
    call = '\t\tCalculateFarSSShadow( SceneDepth, WorldP, WorldP + g_PS_SunLightDir.xyz, CompMatrix, fInShadow, bFcsRecvFol );'
    assert NEW_BLOCK.count(call) == 1
    NEW_BLOCK = NEW_BLOCK.replace(call, '''\t\t// FarContactShadows A/B build: no contact shadows on foliage left of the screen centre.
\t\tif (!(bFcsRecvFol && (IN.ScreenTC.x < 0.5)))
\t''' + call)
    anchor = "\t}\n\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;"
    assert NEW_BLOCK.count(anchor) == 1
    NEW_BLOCK = NEW_BLOCK.replace(anchor, '''\t}

\t// FarContactShadows A/B build: dark line at the screen centre.
\tif (abs(IN.ScreenTC.x - 0.5) < 0.001)
\t\tfInShadow = 0;

#if %_RT_SAMPLE2
\tint lightingModel = lightingModelSSS;''')
if 'abright' in opts:
    assert fol_split and opts.get('abtree') != '1', 'abright= needs folsplit= and no abtree=1'
    anchor = "\t}\n\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;"
    assert NEW_BLOCK.count(anchor) == 1
    NEW_BLOCK = NEW_BLOCK.replace(anchor, '''\t}

\t// FarContactShadows A/B build: dark line at the screen centre.
\tif (abs(IN.ScreenTC.x - 0.5) < 0.001)
\t\tfInShadow = 0;

#if %_RT_SAMPLE2
\tint lightingModel = lightingModelSSS;''')
if opts.get('gbdebug') == '1':
    assert not fol_bands, 'gbdebug=1 and fol bands both draw screen lines'
    anchor = "\t}\n\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;"
    assert NEW_BLOCK.count(anchor) == 1
    NEW_BLOCK = NEW_BLOCK.replace(anchor, "\t}\n" + GB_DEBUG + "\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;")

for old, new, want in ((OLD_STRUCT, NEW_STRUCT, 2), (OLD_VS, NEW_VS, 1),
                       (ANCHOR, FUNC + ANCHOR, 1), (OLD_BLOCK, NEW_BLOCK, 1)):
    n = s.count(old)
    assert n == want, f'expected {want} match(es), got {n}: {old[:60]!r}'
    s = s.replace(old, new)

if opts.get('stamp'):
    # A comment line: changes the source CRC, so every user cache recompiles this build.
    mark = '// FarContactShadows (kcd1-sss)'
    assert s.count(mark) == 1
    s = s.replace(mark, '// ' + opts['stamp'] + '\n' + mark)
os.makedirs(f'{out}/src', exist_ok=True)
mod_src = s.replace('\n', '\r\n').encode('ascii')
open(f'{out}/src/ShadowMaskGen.cfx', 'wb').write(mod_src)
stock_lines = raw.decode('ascii').replace('\r\n', '\n').splitlines(True)
open(f'{out}/src/ShadowMaskGen.diff', 'w').writelines(
    difflib.unified_diff(stock_lines, s.splitlines(True), 'stock/ShadowMaskGen.cfx', 'mod/ShadowMaskGen.cfx'))

mod = f'{out}/FarContactShadows'
os.makedirs(f'{mod}/Data', exist_ok=True)
open(f'{mod}/mod.manifest', 'w', newline='\r\n').write('''<?xml version="1.0" encoding="utf-8"?>
<kcd_mod>
  <info>
    <name>Far Contact Shadows</name>
    <description>Sun screen-space (contact) shadows reach as far as the sun shadow cascades instead of ~3 m. Overrides Shaders/HWScripts/CryFX/ShadowMaskGen.cfx.</description>
    <author>kcd1-sss</author>
    <version>0.4</version>
    <created_on>2026-11-03</created_on>
  </info>
  <supports>
    <kcd_version>1.9.*</kcd_version>
  </supports>
</kcd_mod>
'''.replace('<version>0.4</version>', f'<version>{version}</version>'))
pak = f'{mod}/Data/FarContactShadows.pak'
with zipfile.ZipFile(pak, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('Shaders/HWScripts/CryFX/ShadowMaskGen.cfx', mod_src)
    if opts.get('nosharpen') == '1':
        # Screenshot build: no image sharpening past neutral (the drunk effect sharpens; r_Sharpening does not stop it).
        # Each sharpening amount is capped at 1, so blurring still works. Needs the matching precompiled pixel shaders
        # removed from Engine/shadercache_fcs.pak, or the game keeps the stock ones.
        cryfx = os.path.dirname(stock_path)
        for fn, old, new in (
                ('PostEffects.cfx', 'OUT.Color = lerp(blurredColor, screenColor, psParams[0].w);',
                 'OUT.Color = lerp(blurredColor, screenColor, min(psParams[0].w, 1)); // FarContactShadows nosharpen'),
                ('PostAA.cfx', 'lerp( cFiltered, OUT.Color.rgb * OUT.Color.rgb, vParams.x )',
                 'lerp( cFiltered, OUT.Color.rgb * OUT.Color.rgb, min(vParams.x, 1) ) /* FarContactShadows nosharpen */'),
                ('PostEffectsGame.cfx', 'cImage = lerp(cImageScaledDown, cImage, ColorGradingParams3.w);',
                 'cImage = lerp(cImageScaledDown, cImage, min(ColorGradingParams3.w, 1)); // FarContactShadows nosharpen')):
            src = open(f'{cryfx}/{fn}', 'rb').read().decode('ascii')
            assert src.count(old) == 1, (fn, old)
            z.writestr(f'Shaders/HWScripts/CryFX/{fn}', src.replace(old, new).encode('ascii'))
    if opts.get('lookup'):
        # Mods-folder-only route: a lookupdata.bin without the stock DeferredShadow records, so the engine
        # treats those precompiled shaders as missing and compiles this source (tools/scripts/patch_lookupdata.py).
        for lp in ('Shaders/Cache/D3D11/lookupdata.bin', 'ShaderCache/D3D11/lookupdata.bin'):
            z.write(opts['lookup'], lp)
    if stub_dir:
        for sub in ('cgpshaders', 'cgvshaders'):
            for fn in sorted(os.listdir(f'{stub_dir}/{sub}')):
                z.write(f'{stub_dir}/{sub}/{fn}', f'Shaders/Cache/D3D11/{sub}/{fn}')
print('wrote', f'{out}/src/ShadowMaskGen.cfx', pak, len(mod_src), 'bytes source')
