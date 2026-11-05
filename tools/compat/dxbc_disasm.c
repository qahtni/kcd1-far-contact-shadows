/* dxbc_disasm: print the disassembly of a compiled DXBC shader with the given d3dcompiler_47.dll.
   usage: dxbc_disasm.exe DLL FILE.dxbc
   Build: x86_64-w64-mingw32-gcc -O1 -o dxbc_disasm.exe dxbc_disasm.c */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct Blob Blob;
struct BlobVtbl {
    void *qi; void *addref; ULONG (WINAPI *Release)(Blob *);
    void *(WINAPI *GetBufferPointer)(Blob *); SIZE_T (WINAPI *GetBufferSize)(Blob *);
};
struct Blob { struct BlobVtbl *v; };
typedef HRESULT (WINAPI *PFN_disasm)(const void *, SIZE_T, UINT, const char *, Blob **);

int main(int argc, char **argv)
{
    if (argc < 3) { fprintf(stderr, "usage: dxbc_disasm DLL FILE.dxbc\n"); return 2; }
    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 2; }
    PFN_disasm disasm = (PFN_disasm)GetProcAddress(h, "D3DDisassemble");
    if (!disasm) { fprintf(stderr, "no D3DDisassemble export\n"); return 2; }
    FILE *f = fopen(argv[2], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[2]); return 2; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = malloc(n); fread(buf, 1, n, f); fclose(f);
    Blob *out = NULL;
    HRESULT hr = disasm(buf, (SIZE_T)n, 0, NULL, &out);
    if (out) { fwrite(out->v->GetBufferPointer(out), 1, out->v->GetBufferSize(out) - 1, stdout); out->v->Release(out); }
    fprintf(stderr, "hr=0x%08lx\n", (unsigned long)hr);
    return FAILED(hr) ? 1 : 0;
}
