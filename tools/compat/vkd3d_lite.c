/* vkd3d_lite: compile one HLSL file with a given libvkd3d-shader-1.dll (the compiler Proton's
   d3dcompiler_47 uses), print its messages. Same job as fxc_lite.exe, for Proton.
   usage: vkd3d_lite.exe DLL FILE ENTRY PROFILE [NAME:VALUE ...]
   NAME:VALUE are compile options as numbers, e.g. 8:1 = BACKWARD_COMPATIBILITY / MAP_SEMANTIC_NAMES
   (Wine's d3dcompiler sets that one for D3DCOMPILE_ENABLE_BACKWARDS_COMPATIBILITY).
   Exit code 0 only if the compile succeeds.
   Build: x86_64-w64-mingw32-gcc -O1 -o vkd3d_lite.exe vkd3d_lite.c
   Structure and enum values from vkd3d_shader.h (stable since vkd3d 1.2). */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

struct code { const void *code; size_t size; };
struct hlsl_source_info {
    int type; const void *next; const char *entry_point; struct code secondary_code; const char *profile;
};
struct option { int name; unsigned int value; };
struct compile_info {
    int type; const void *next; struct code source; int source_type; int target_type;
    const void *options; unsigned int option_count; int log_level; const char *source_name;
};
enum { ST_COMPILE_INFO = 0, ST_HLSL_SOURCE_INFO = 6 };
enum { SOURCE_HLSL = 2 };
enum { TARGET_DXBC_TPF = 5 };
enum { LOG_INFO = 3 };

typedef int (*PFN_compile)(const struct compile_info *, struct code *, char **);
typedef void (*PFN_free_messages)(char *);
typedef void (*PFN_free_code)(struct code *);
typedef const char *(*PFN_version)(unsigned int *, unsigned int *);

int main(int argc, char **argv)
{
    if (argc < 5) { fprintf(stderr, "usage: vkd3d_lite DLL FILE ENTRY PROFILE\n"); return 2; }
    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 2; }
    PFN_compile compile = (PFN_compile)GetProcAddress(h, "vkd3d_shader_compile");
    PFN_free_messages free_messages = (PFN_free_messages)GetProcAddress(h, "vkd3d_shader_free_messages");
    PFN_free_code free_code = (PFN_free_code)GetProcAddress(h, "vkd3d_shader_free_shader_code");
    PFN_version version = (PFN_version)GetProcAddress(h, "vkd3d_shader_get_version");
    if (!compile) { fprintf(stderr, "no vkd3d_shader_compile export\n"); return 2; }
    if (version) printf("%s\n", version(NULL, NULL));

    FILE *f = fopen(argv[2], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[2]); return 2; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *src = malloc(n + 1); fread(src, 1, n, f); src[n] = 0; fclose(f);

    struct hlsl_source_info hlsl = { ST_HLSL_SOURCE_INFO, NULL, argv[3], { NULL, 0 }, argv[4] };
    struct option opts[16]; unsigned int nopt = 0;
    for (int i = 5; i < argc && nopt < 16; i++)
        if (sscanf(argv[i], "%i:%i", &opts[nopt].name, (int *)&opts[nopt].value) == 2) nopt++;
    struct compile_info info = { ST_COMPILE_INFO, &hlsl, { src, (size_t)n }, SOURCE_HLSL, TARGET_DXBC_TPF,
                                 nopt ? opts : NULL, nopt, LOG_INFO, argv[2] };
    struct code out = { NULL, 0 };
    char *messages = NULL;
    int ret = compile(&info, &out, &messages);
    if (messages) { fputs(messages, stdout); if (free_messages) free_messages(messages); }
    printf("ret=%d bytecode=%lu\n", ret, (unsigned long)out.size);
    if (out.code && free_code) free_code(&out);
    return ret == 0 ? 0 : 1;
}
