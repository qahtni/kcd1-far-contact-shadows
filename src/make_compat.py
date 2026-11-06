#!/usr/bin/env python3
"""Make the FarContactShadows shader build with every shader compiler the game meets.

usage: make_compat.py MOD_ShadowMaskGen.cfx OUT_DIR [version=V] [ownsurface=1] [nocloth=1 [speckeys=1 [decalkeys=1]] [clothblock=1] [backlit=1] [sheet=1] [clothdebug=1]]

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

# nocloth=1 (1.0.2): no contact shadows on cloth where the sun shines through it. Tents, flags and curtains are
# drawn with the foliage shader as translucent sheets; inside a tent the ray toward the sun passes through the
# curved sheet and its folds read as blockers (dark wedges). Cloth is recognised by translucency presets no plant
# uses (material scan of every pak, work/cloth_scan/): grey with stored luma byte 77-86 or 90-92 (main preset
# 0.456 x 0.25 = byte 85), or the orange curtain preset. The sun shines through when the ray's end lies behind
# the receiver's own plane (from ownsurface). The sunlit side keeps its contact shadows.
CLOTH_HELPER = """// FarContactShadows nocloth: world cloth (tents, flags, curtains) by its translucency preset; no plant uses these.
bool FcsIsCloth(float4 bufferA, float4 bufferB, float4 bufferC)
{
	if ((FcsLightingModel(bufferA) != LIGHTINGMODEL_TRANSMITTANCE) || ((bufferB.w * TWO_BITS_EXTRACTION_FACTOR) >= 1.0))
		return false;
	// Stored bytes: luma (with the lighting model in the top bits), Cb, Cr.
	const float3 vB = floor(float3(bufferA.w, bufferC.z, bufferC.w) * 255.0 + 0.5);
	const bool bGrey = (abs(vB.y - 127) <= 1) && (abs(vB.z - 127) <= 1);
	if (bGrey && (((vB.x >= 77) && (vB.x <= 86)) || ((vB.x >= 90) && (vB.x <= 92))))
		return true;
	// Orange preset (0.991, 0.584, 0.262): castle curtains and the Vranik canopy.
	const bool bOrange1 = (abs(vB.x - 80) <= 1) && (abs(vB.y - 120) <= 1) && (abs(vB.z - 132) <= 1);
	const bool bOrange2 = (abs(vB.x - 89) <= 1) && (abs(vB.y - 117) <= 1) && (abs(vB.z - 136) <= 1);
	return bOrange1 || bOrange2;
}

"""
CLOTH_TEST = """
	// No contact shadows where the sun shines through cloth (e.g. inside a tent): the ray toward the sun then ends
	// behind the cloth's own plane, and its folds would read as blockers.
	float fFcsClothKeep = 1;
	if (bFcsCloth)
	{
		const float4 vFcsEnd = vTC1 / vTC1.w;
		const float2 vFcsEndPix = float2(vFcsEnd.x * 0.5 + 0.5, 0.5 - vFcsEnd.y * 0.5) * PS_ScreenSize.xy;
		const float fFcsIzEnd = 1.0 / max(g_PS_ProjRatio.y / (vFcsEnd.z - g_PS_ProjRatio.x), 1e-6);
		const float fFcsIzPlaneEnd = fFcsIz0 + fFcsGx * (vFcsEndPix.x - ((float)vFcsPix0.x + 0.5)) + fFcsGy * (vFcsEndPix.y - ((float)vFcsPix0.y + 0.5));
		if (fFcsIzEnd < fFcsIzPlaneEnd)
			fFcsClothKeep = 0;
	}
"""
# backlit=1 (1.0.2): the cloth presets miss tents on the grass default preset (Cuman v4 tents, the Merhojed camp:
# stored bytes 126/113/129, same as most grass). General rule instead: where the sun shines through a thin translucent
# surface, a blocker must lie on the sun's side of it, i.e. behind the receiver's plane. Anything on the camera side
# cannot shade it: seen from inside a tent that is the rest of the curved wall, the poles and the floor. Grass and
# leaves keep the blockers behind them (the only ones that can shade a back-lit sheet). Used only where the plane is
# trustworthy (one neighbour pair agrees on the slope), so noisy distant foliage keeps the 1.0.1 behaviour.
BACKLIT_TEST = """
	// Does the sun shine through the receiver? Then the ray toward it ends behind the receiver's own plane.
	const float4 vFcsEnd = vTC1 / vTC1.w;
	const float2 vFcsEndPix = float2(vFcsEnd.x * 0.5 + 0.5, 0.5 - vFcsEnd.y * 0.5) * PS_ScreenSize.xy;
	const float fFcsIzEnd = 1.0 / max(g_PS_ProjRatio.y / (vFcsEnd.z - g_PS_ProjRatio.x), 1e-6);
	const float fFcsIzPlaneEnd = fFcsIz0 + fFcsGx * (vFcsEndPix.x - ((float)vFcsPix0.x + 0.5)) + fFcsGy * (vFcsEndPix.y - ((float)vFcsPix0.y + 0.5));
	const bool bFcsBehind = fFcsIzEnd < fFcsIzPlaneEnd;
	// Cloth by its preset: no contact shadows at all where the sun shines through (e.g. inside a tent).
	const float fFcsClothKeep = (bFcsCloth && bFcsBehind) ? 0 : 1;
	// Any other translucent receiver with the sun behind it: only blockers behind its plane count (below, in the loop).
	// The plane must be trustworthy: the two neighbours of at least one pair agree on the slope.
	const float fFcsFlatTol = 0.0005 * fFcsIz0;
	const bool bFcsFlat = (abs(fFcsIzR - fFcsIzL) <= 0.5 * min(abs(fFcsIzR), abs(fFcsIzL)) + fFcsFlatTol)
		|| (abs(fFcsIzD - fFcsIzU) <= 0.5 * min(abs(fFcsIzD), abs(fFcsIzU)) + fFcsFlatTol);
	const bool bFcsBackLit = bFcsRecvFol && bFcsBehind && bFcsFlat;
"""
BACKLIT_LOOP = """		// Sun shining through the receiver: a blocker on the camera side of its plane cannot shade it.
		if (bFcsBackLit && (fFcsIzScr >= fFcsIzPlane))
			fFcsOcc = 0;
		fFcsOccMax = max(fFcsOccMax, fFcsOcc);
"""
# sheet=1 (1.0.2, replaces backlit=1, which did not remove the wedges on the Cuman v4 tents): what works for preset
# cloth (no contact shadows where the sun shines through) for every translucent sheet. A sheet is smooth over R pixels
# each way in both axes (R = screen height / 135: 16 px at 2160p, 8 at 1080p), which blades of grass and most leaves
# are not; its slope over 2R pixels also gives a steadier plane than the 1-pixel neighbours for the sun-behind test.
SHEET_TEST = """
	// Does the sun shine through the receiver? Then the ray toward it ends behind the receiver's own plane.
	const float4 vFcsEnd = vTC1 / vTC1.w;
	const float2 vFcsEndOff = float2(vFcsEnd.x * 0.5 + 0.5, 0.5 - vFcsEnd.y * 0.5) * PS_ScreenSize.xy - (float2(vFcsPix0) + 0.5);
	const float fFcsIzEnd = 1.0 / max(g_PS_ProjRatio.y / (vFcsEnd.z - g_PS_ProjRatio.x), 1e-6);
	const bool bFcsBehind = fFcsIzEnd < fFcsIz0 + fFcsGx * vFcsEndOff.x + fFcsGy * vFcsEndOff.y;
	// Translucent sheets on any preset (e.g. the Cuman v4 tents, which share grass's default value): smooth over
	// R pixels each way in both axes. Blades of grass and most leaves are not.
	bool bFcsSheetBehind = false;
	if (bFcsRecvFol)
	{
		const int nFcsR = max(4, (int)(PS_ScreenSize.y / 135.0));
		const float fFcsXP = 1.0 / max(FcsSceneDepthPix(vFcsPix0 + int2(nFcsR, 0)), 1e-6) - fFcsIz0;
		const float fFcsXN = fFcsIz0 - 1.0 / max(FcsSceneDepthPix(vFcsPix0 - int2(nFcsR, 0)), 1e-6);
		const float fFcsYP = 1.0 / max(FcsSceneDepthPix(vFcsPix0 + int2(0, nFcsR)), 1e-6) - fFcsIz0;
		const float fFcsYN = fFcsIz0 - 1.0 / max(FcsSceneDepthPix(vFcsPix0 - int2(0, nFcsR)), 1e-6);
		const float fFcsSheetTol = 0.003 * fFcsIz0;
		const bool bFcsSheet = (abs(fFcsXP - fFcsXN) <= 0.25 * min(abs(fFcsXP), abs(fFcsXN)) + fFcsSheetTol)
			&& (abs(fFcsYP - fFcsYN) <= 0.25 * min(abs(fFcsYP), abs(fFcsYN)) + fFcsSheetTol);
		const float2 vFcsWG = float2(fFcsXP + fFcsXN, fFcsYP + fFcsYN) / (2.0 * (float)nFcsR);
		bFcsSheetBehind = bFcsSheet && (fFcsIzEnd < fFcsIz0 + dot(vFcsWG, vFcsEndOff));
	}
	// No contact shadows where the sun shines through cloth (preset) or any other translucent sheet.
	const float fFcsClothKeep = ((bFcsCloth && bFcsBehind) || bFcsSheetBehind) ? 0 : 1;
"""
# sheet=1 backlit=1 together (1.0.2): sheet test as above; where it fails (a fold seen edge-on, next to the floor or a
# pole: thin dark lines in the sheet-only build) the back-lit rule takes over. Its blockers are only a few pixels
# away there, so the 1-pixel plane is good enough.
SHEET_BACKLIT = """	// Not a sheet here (a fold seen edge-on, next to the floor or a pole) but the sun is behind: only blockers behind
	// the receiver's plane count (in the loop). The plane must be trustworthy: one neighbour pair agrees on the slope.
	const float fFcsFlatTol = 0.0005 * fFcsIz0;
	const bool bFcsFlat = (abs(fFcsIzR - fFcsIzL) <= 0.5 * min(abs(fFcsIzR), abs(fFcsIzL)) + fFcsFlatTol)
		|| (abs(fFcsIzD - fFcsIzU) <= 0.5 * min(abs(fFcsIzD), abs(fFcsIzU)) + fFcsFlatTol);
	const bool bFcsBackLit = bFcsRecvFol && bFcsBehind && bFcsFlat && (fFcsClothKeep > 0.5);
"""
# speckeys=1 (1.0.2): cloth on translucency presets that plants also use (Cuman v4 and "prib" tents, the main Cuman
# tent fabric, bath tents, gamblers' barn cloth, wind sock, clothes line, Rataje tavern cloth) is told apart by the
# stored specular byte too: the foliage shader writes sqrt(material Specular) there (none of these has a specular map
# or terrain blend). Material scan (work/cloth_scan/veg2.tsv): no plant shares value + specular, except the Vranik
# palisade grass (v4 tents a-e) and small forest roots plus a hawthorn shadow proxy (v4 tent f).
CLOTH_SPECKEYS = """	// Cloth on presets plants also use: value plus the specular byte (bufferC.y, sqrt of the material Specular).
	const float4 vK = float4(vB, floor(bufferC.y * 255.0 + 0.5));
	if (FcsKey(vK, float4(126, 113, 129, 24)) || FcsKey(vK, float4(126, 113, 129, 25)) || FcsKey(vK, float4(126, 113, 129, 46))
		|| FcsKey(vK, float4(121, 114, 129, 48)) || FcsKey(vK, float4(64, 127, 127, 46)) || FcsKey(vK, float4(95, 120, 128, 25))
		|| FcsKey(vK, float4(98, 119, 128, 41)) || FcsKey(vK, float4(66, 127, 127, 41)) || FcsKey(vK, float4(107, 127, 127, 50))
		|| FcsKey(vK, float4(109, 117, 129, 30)))
		return true;
"""
# decalkeys=1 (needs speckeys=1): the Cuman v4 and bath tents carry seam decals (Illum %DECAL "alpha_seams", Specular
# 0.0356: stored as Cb 127, specular byte 48) along the floor hem and some seams. The Z pass blends Cb and the specular
# byte toward the decal's by the decal's alpha, so the plain keys miss there and the hem kept contact shadows (dark
# line where the tent meets the floor). Luma and Cr sit in the alpha channels, which decals keep (their alpha output is
# the blend factor). Rule: luma within 1, Cr exact, Cb moved toward 127 by at least 1, and (Cb, specular byte) within
# 1.5 of the line from the key to (127, 48). No foliage material in the scan of all 363 translucent foliage-shader
# materials matches it; Cr exact keeps out the sick-oak leaves (126/118/128, spec 33), which sit on the v4 line.
CLOTH_DECALFN = """// Stored bytes of a key under a seam decal (Cb and specular byte blended toward 127 and 48).
bool FcsKeyDecal(float4 v, float4 k)
{
	if ((abs(v.x - k.x) > 1) || (abs(v.z - k.z) > 0.5) || (v.y < k.y + 1) || (v.y > 128))
		return false;
	const float2 vD = float2(127.0 - k.y, 48.0 - k.w);
	const float2 vP = float2(v.y - k.y, v.w - k.w);
	const float t = saturate(dot(vP, vD) / dot(vD, vD));
	return length(vP - t * vD) <= 1.5;
}

"""
CLOTH_DECALKEYS = """	// Same cloth under its seam decals (floor hem, seams).
	if (FcsKeyDecal(vK, float4(126, 113, 129, 24)) || FcsKeyDecal(vK, float4(126, 113, 129, 25)) || FcsKeyDecal(vK, float4(126, 113, 129, 46))
		|| FcsKeyDecal(vK, float4(121, 114, 129, 48)) || FcsKeyDecal(vK, float4(95, 120, 128, 25)) || FcsKeyDecal(vK, float4(98, 119, 128, 41))
		|| FcsKeyDecal(vK, float4(109, 117, 129, 30)))
		return 4;
"""
CLOTH_ISCLOTH = """
bool FcsIsCloth(float4 bufferA, float4 bufferB, float4 bufferC)
{
	return FcsClothClass(bufferA, bufferB, bufferC) > 0;
}
"""
# clothblock=1 (needs nocloth=1): world cloth casts no contact shadows. The sun shadow maps let the sun through tent
# walls (the floor inside a tent is sunlit, with shadows of the poles and props), but the ray found the wall as a
# blocker: dark blades on the floor and on the bottom of the wall where it bends toward the floor (shots 032856,
# 032900). Checked only for foliage-type blockers that would raise the shadow, so the extra G-buffer read is rare.
CLOTH_BLOCK_LOOP = """		// World cloth lets the sun through (as in the sun shadow maps): it casts no contact shadows.
		[branch] if (bFcsFol && (fFcsOcc > fFcsOccMax))
		{
			if (FcsIsCloth(sceneGBufferA[vFcsPix], sceneGBufferB[vFcsPix], sceneGBufferC[vFcsPix]))
				fFcsOcc = 0;
		}
"""
CLOTH_KEYFN = """// Stored bytes match a key within 1.
bool FcsKey(float4 v, float4 k)
{
	const float4 d = abs(v - k);
	return max(max(d.x, d.y), max(d.z, d.w)) <= 1;
}

"""
# clothdebug=1: test build. Left half of the screen: cloth where the sun shines through = "/" stripes, cloth on its
# sunlit side = thin "\\" lines, other translucent surfaces (foliage, other cloth) = thin horizontal lines,
# characters (skin profile or 3PL) = dots. Probe right of and below the crosshair: the G-buffer bytes under the
# screen centre as 4 rows of 8 bits (dark = 1) between dark end blocks: luma byte, Cb, Cr, profile byte. With
# decalkeys=1 the probe sits right of and above the crosshair with 7 rows: luma, Cb, Cr, specular byte, smoothness,
# profile byte, cloth class (0 none, 1 grey preset, 2 orange preset, 3 specular key, 4 key under a seam decal).
# Marks are shadow, so they show on sunlit surfaces only.
CLOTH_DEBUG = """
	// FarContactShadows clothdebug (test build only).
	{
		const float2 vFcsP = IN.ScreenTC.xy * PS_ScreenSize.xy;
		const bool bFcsProfile = (sceneGBufferB[pixelCoord].w * TWO_BITS_EXTRACTION_FACTOR) >= 1.0;
		bool bFcsMark = false;
		if (vFcsP.x < PS_ScreenSize.x * 0.5)
		{
			if (bFcsCloth)
				bFcsMark = (fFcsDbgKeep < 0.5) ? (frac((vFcsP.x + vFcsP.y) / 24) < 0.5) : (frac((vFcsP.x - vFcsP.y) / 24) < 0.15);
			else if ((lightingModelSSS == LIGHTINGMODEL_TRANSMITTANCE) && !bFcsProfile)
				bFcsMark = frac(vFcsP.y / 24) < 0.15;
			else if (bFcsProfile)
				bFcsMark = (frac(vFcsP.x / 12) < 0.4) && (frac(vFcsP.y / 12) < 0.4);
		}
		const int2 vFcsC = int2(PS_ScreenSize.xy * 0.5);
		const int2 vFcsR = int2(vFcsP) - vFcsC - int2(48, 48);
		if ((vFcsR.x >= 0) && (vFcsR.y >= 0) && (vFcsR.x < 160) && (vFcsR.y < 64))
		{
			const uint2 vFcsU = uint2(vFcsR);
			const uint nFcsCol = vFcsU.x >> 4;
			const uint nFcsRow = vFcsU.y >> 4;
			const float4 vFcsCA = sceneGBufferA[vFcsC];
			const float4 vFcsCB = sceneGBufferB[vFcsC];
			const float4 vFcsCC = sceneGBufferC[vFcsC];
			const float fFcsVal = (nFcsRow == 0) ? vFcsCA.w : ((nFcsRow == 1) ? vFcsCC.z : ((nFcsRow == 2) ? vFcsCC.w : vFcsCB.w));
			const uint nFcsByte = (uint)(fFcsVal * 255.0 + 0.5);
			const bool bFcsBit = ((nFcsCol == 0) || (nFcsCol == 9)) ? true : (((nFcsByte >> (8 - nFcsCol)) & 1) == 1);
			bFcsMark = bFcsBit && ((vFcsU.x & 15) < 12) && ((vFcsU.y & 15) < 12);
		}
		if (bFcsMark)
			fInShadow = 0;
	}
"""
if opts.get('clothdebug') == '1':
    assert opts.get('nocloth') == '1', 'clothdebug=1 needs nocloth=1'
if opts.get('decalkeys') == '1':
    assert opts.get('speckeys') == '1', 'decalkeys=1 needs speckeys=1'
if opts.get('clothblock') == '1':
    assert opts.get('nocloth') == '1', 'clothblock=1 needs nocloth=1'
if opts.get('backlit') == '1' or opts.get('sheet') == '1':
    assert opts.get('nocloth') == '1', 'backlit=1 and sheet=1 need nocloth=1'
if opts.get('nocloth') == '1':
    assert opts.get('ownsurface') == '1', 'nocloth=1 needs ownsurface=1 (uses its plane)'
    dbg = opts.get('clothdebug') == '1'
    if opts.get('speckeys') == '1':
        CLOTH_HELPER = rep(CLOTH_HELPER, '\treturn bOrange1 || bOrange2;\n', '\tif (bOrange1 || bOrange2)\n\t\treturn true;\n' + CLOTH_SPECKEYS + '\treturn false;\n')
        CLOTH_HELPER = rep(CLOTH_HELPER, '// FarContactShadows nocloth: world cloth', CLOTH_KEYFN + '// FarContactShadows nocloth: world cloth')
        if opts.get('decalkeys') == '1':
            # Class instead of yes/no (0 none, 1 grey preset, 2 orange preset, 3 key, 4 key under a seam decal).
            CLOTH_HELPER = rep(CLOTH_HELPER, '\t\treturn true;\n\treturn false;\n}\n', '\t\treturn 3;\n' + CLOTH_DECALKEYS + '\treturn 0;\n}\n' + CLOTH_ISCLOTH)
            CLOTH_HELPER = rep(CLOTH_HELPER, '\t\treturn true;\n\t// Orange preset', '\t\treturn 1;\n\t// Orange preset')
            CLOTH_HELPER = rep(CLOTH_HELPER, '\tif (bOrange1 || bOrange2)\n\t\treturn true;\n', '\tif (bOrange1 || bOrange2)\n\t\treturn 2;\n')
            CLOTH_HELPER = rep(CLOTH_HELPER, '\t\treturn false;\n', '\t\treturn 0;\n')
            CLOTH_HELPER = rep(CLOTH_HELPER, 'bool FcsIsCloth(float4 bufferA, float4 bufferB, float4 bufferC)\n{\n\tif',
                               'float FcsClothClass(float4 bufferA, float4 bufferB, float4 bufferC)\n{\n\tif')
            CLOTH_HELPER = rep(CLOTH_HELPER, '// FarContactShadows nocloth: world cloth', CLOTH_DECALFN + '// FarContactShadows nocloth: world cloth')
    s = rep(s, '// FarContactShadows (kcd1-sss): sun screen-space shadows that reach as far as the sun shadow cascades.\n',
               CLOTH_HELPER + '// FarContactShadows (kcd1-sss): sun screen-space shadows that reach as far as the sun shadow cascades.\n')
    s = rep(s, 'inout float fInShadow, const bool bFcsRecvFol, const int2 vFcsPix0)',
               'inout float fInShadow, const bool bFcsRecvFol, const int2 vFcsPix0, const bool bFcsCloth'
               + (', inout float fFcsDbgKeep)' if dbg else ')'))
    if opts.get('sheet') == '1' and opts.get('backlit') == '1':
        s = rep(s, '\tfloat fFcsOccMax = 0;\n', '\tfloat fFcsOccMax = 0;\n' + SHEET_TEST + SHEET_BACKLIT
                   + ('\tfFcsDbgKeep = bFcsCloth ? fFcsClothKeep : (bFcsSheetBehind ? 2 : (bFcsBackLit ? 3 : 1));\n' if dbg else ''))
        s = rep(s, '\t\tfFcsOccMax = max(fFcsOccMax, fFcsOcc);\n', BACKLIT_LOOP)
    elif opts.get('sheet') == '1':
        s = rep(s, '\tfloat fFcsOccMax = 0;\n', '\tfloat fFcsOccMax = 0;\n' + SHEET_TEST
                   + ('\tfFcsDbgKeep = bFcsCloth ? fFcsClothKeep : (bFcsSheetBehind ? 2 : 1);\n' if dbg else ''))
    elif opts.get('backlit') == '1':
        s = rep(s, '\tfloat fFcsOccMax = 0;\n', '\tfloat fFcsOccMax = 0;\n' + BACKLIT_TEST
                   + ('\tfFcsDbgKeep = bFcsCloth ? fFcsClothKeep : (bFcsBackLit ? 2 : 1);\n' if dbg else ''))
        s = rep(s, '\t\tfFcsOccMax = max(fFcsOccMax, fFcsOcc);\n', BACKLIT_LOOP)
    else:
        s = rep(s, '\tfloat fFcsOccMax = 0;\n', '\tfloat fFcsOccMax = 0;\n' + CLOTH_TEST + ('\tfFcsDbgKeep = fFcsClothKeep;\n' if dbg else ''))
    if opts.get('clothblock') == '1':
        s = rep(s, '\t\tfFcsOccMax = max(fFcsOccMax, fFcsOcc);\n', CLOTH_BLOCK_LOOP + '\t\tfFcsOccMax = max(fFcsOccMax, fFcsOcc);\n')
    s = rep(s, '\tfloat fInSSS = 1 - fFcsOccMax;', '\tfloat fInSSS = 1 - fFcsOccMax * fFcsClothKeep;')
    s = rep(s, '\tint lightingModelSSS = FcsLightingModel(sceneGBufferA[pixelCoord]);\n',
               '\tint lightingModelSSS = FcsLightingModel(sceneGBufferA[pixelCoord]);\n'
               '\t// FarContactShadows nocloth: is this world cloth (tents, flags, curtains)?\n'
               '\tconst bool bFcsCloth = FcsIsCloth(sceneGBufferA[pixelCoord], sceneGBufferB[pixelCoord], sceneGBufferC[pixelCoord]);\n'
               + ('\tfloat fFcsDbgKeep = 1;\n' if dbg else ''))
    s = rep(s, 'CompMatrix, fInShadow, bFcsRecvFol, vFcsPix0 );',
               'CompMatrix, fInShadow, bFcsRecvFol, vFcsPix0, bFcsCloth' + (', fFcsDbgKeep );' if dbg else ' );'))
    if dbg:
        if opts.get('backlit') == '1' and opts.get('sheet') == '1':
            # Other translucent surfaces: vertical lines = sheet (skipped), dashed vertical lines = back-lit rule, horizontal = neither.
            CLOTH_DEBUG = rep(CLOTH_DEBUG, 'bFcsMark = frac(vFcsP.y / 24) < 0.15;',
                              'bFcsMark = (fFcsDbgKeep > 2.5) ? ((frac(vFcsP.x / 24) < 0.15) && (frac(vFcsP.y / 8) < 0.5))'
                              ' : ((fFcsDbgKeep > 1.5) ? (frac(vFcsP.x / 24) < 0.15) : (frac(vFcsP.y / 24) < 0.15));')
        elif opts.get('backlit') == '1' or opts.get('sheet') == '1':
            # Other translucent surfaces: vertical lines where the back-lit (or sheet) rule is on, horizontal lines elsewhere.
            CLOTH_DEBUG = rep(CLOTH_DEBUG, 'bFcsMark = frac(vFcsP.y / 24) < 0.15;',
                              'bFcsMark = (fFcsDbgKeep > 1.5) ? (frac(vFcsP.x / 24) < 0.15) : (frac(vFcsP.y / 24) < 0.15);')
        if opts.get('speckeys') == '1':
            CLOTH_DEBUG = rep(CLOTH_DEBUG, '(vFcsR.y < 64)', '(vFcsR.y < 96)')
            CLOTH_DEBUG = rep(CLOTH_DEBUG, ': ((nFcsRow == 2) ? vFcsCC.w : vFcsCB.w));',
                              ': ((nFcsRow == 2) ? vFcsCC.w : ((nFcsRow == 3) ? vFcsCC.y : ((nFcsRow == 4) ? vFcsCC.x : vFcsCB.w))));')
        if opts.get('decalkeys') == '1':
            # Probe above the crosshair (aim at the floor hem; the probe then sits on the lit wall), 7th row = class.
            CLOTH_DEBUG = rep(CLOTH_DEBUG, 'vFcsC - int2(48, 48);', 'vFcsC - int2(48, -160);')
            CLOTH_DEBUG = rep(CLOTH_DEBUG, '(vFcsR.y < 96)', '(vFcsR.y < 112)')
            CLOTH_DEBUG = rep(CLOTH_DEBUG, 'vFcsCC.x : vFcsCB.w))));',
                              'vFcsCC.x : ((nFcsRow == 5) ? vFcsCB.w : FcsClothClass(vFcsCA, vFcsCB, vFcsCC) / 255.0)))));')
            CLOTH_DEBUG = rep(CLOTH_DEBUG, '\t\t\tif (bFcsCloth)\n\t\t\t\tbFcsMark = (fFcsDbgKeep < 0.5) ? (frac((vFcsP.x + vFcsP.y) / 24) < 0.5) : (frac((vFcsP.x - vFcsP.y) / 24) < 0.15);',
                              '\t\t\tconst float fFcsPer = (FcsClothClass(sceneGBufferA[pixelCoord], sceneGBufferB[pixelCoord], sceneGBufferC[pixelCoord]) > 3.5) ? 10 : 24;\n'
                              '\t\t\tif (bFcsCloth)\n\t\t\t\tbFcsMark = (fFcsDbgKeep < 0.5) ? (frac((vFcsP.x + vFcsP.y) / fFcsPer) < 0.5) : (frac((vFcsP.x - vFcsP.y) / fFcsPer) < 0.15);')
        s = rep(s, '\t}\n\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;',
                   '\t}\n' + CLOTH_DEBUG + '\n#if %_RT_SAMPLE2\n\tint lightingModel = lightingModelSSS;')

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
