/* fxc_lite: compile one HLSL file with a given d3dcompiler DLL, print errors/warnings.
   usage: fxc_lite.exe DLL FILE ENTRY TARGET FLAGS_HEX [NAME=VALUE ...]
   Exit code 0 only if D3DCompile succeeds. Build: x86_64-w64-mingw32-gcc -O1 -o fxc_lite.exe fxc_lite.c */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *Name; const char *Definition; } Macro;
typedef struct Blob Blob;
typedef struct {
    void *QueryInterface, *AddRef;
    ULONG (WINAPI *Release)(Blob *);
    LPVOID (WINAPI *GetBufferPointer)(Blob *);
    SIZE_T (WINAPI *GetBufferSize)(Blob *);
} BlobVtbl;
struct Blob { BlobVtbl *v; };
typedef HRESULT (WINAPI *PD3DCompile)(LPCVOID, SIZE_T, LPCSTR, const Macro *, void *, LPCSTR,
                                      LPCSTR, UINT, UINT, Blob **, Blob **);

int main(int argc, char **argv)
{
    if (argc < 6) { fprintf(stderr, "usage: fxc_lite DLL FILE ENTRY TARGET FLAGS_HEX [N=V...]\n"); return 2; }
    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 2; }
    PD3DCompile compile = (PD3DCompile)GetProcAddress(h, "D3DCompile");
    if (!compile) { fprintf(stderr, "no D3DCompile export\n"); return 2; }

    FILE *f = fopen(argv[2], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[2]); return 2; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *src = malloc(n + 1); fread(src, 1, n, f); src[n] = 0; fclose(f);

    Macro m[33]; int k = 0;
    for (int i = 6; i < argc && k < 32; i++) {
        char *eq = strchr(argv[i], '=');
        if (eq) { *eq = 0; m[k].Name = argv[i]; m[k].Definition = eq + 1; k++; }
    }
    m[k].Name = NULL; m[k].Definition = NULL;

    UINT flags = (UINT)strtoul(argv[5], NULL, 16);
    Blob *code = NULL, *err = NULL;
    HRESULT hr = compile(src, n, argv[2], m, NULL, argv[3], argv[4], flags, 0, &code, &err);
    if (err) {
        fwrite(err->v->GetBufferPointer(err), 1, err->v->GetBufferSize(err), stdout);
        err->v->Release(err);
    }
    printf("\nhr=0x%08lx bytecode=%lu\n", (unsigned long)hr,
           code ? (unsigned long)code->v->GetBufferSize(code) : 0UL);
    const char *out = getenv("FXC_OUT");  /* optional: save the compiled bytecode there */
    if (code && out) { FILE *w = fopen(out, "wb"); if (w) { fwrite(code->v->GetBufferPointer(code), 1, code->v->GetBufferSize(code), w); fclose(w); } }
    if (code) code->v->Release(code);
    return FAILED(hr) ? 1 : 0;
}
