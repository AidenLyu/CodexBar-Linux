#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <sys/types.h>
#include <sys/stat.h>

static const char *redirect_path(const char *pathname) {
    if (pathname && (
        strcmp(pathname, "/etc/ssl/certs/ca-certificates.crt") == 0 ||
        strcmp(pathname, "/etc/pki/tls/certs/ca-bundle.crt") == 0 ||
        strcmp(pathname, "/etc/ssl/ca-bundle.pem") == 0 ||
        strcmp(pathname, "/var/lib/ca-certificates/ca-bundle.pem") == 0
    )) {
        const char *custom = getenv("CUSTOM_CA_BUNDLE");
        if (custom) {
            return custom;
        }
    }
    return pathname;
}

typedef int (*orig_open_t)(const char *pathname, int flags, ...);
int open(const char *pathname, int flags, ...) {
    orig_open_t orig = (orig_open_t)dlsym(RTLD_NEXT, "open");
    pathname = redirect_path(pathname);
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode_t mode = va_arg(args, mode_t);
        va_end(args);
        return orig(pathname, flags, mode);
    }
    return orig(pathname, flags);
}

typedef int (*orig_open64_t)(const char *pathname, int flags, ...);
int open64(const char *pathname, int flags, ...) {
    orig_open64_t orig = (orig_open64_t)dlsym(RTLD_NEXT, "open64");
    pathname = redirect_path(pathname);
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode_t mode = va_arg(args, mode_t);
        va_end(args);
        return orig(pathname, flags, mode);
    }
    return orig(pathname, flags);
}

typedef int (*orig_openat_t)(int dirfd, const char *pathname, int flags, ...);
int openat(int dirfd, const char *pathname, int flags, ...) {
    orig_openat_t orig = (orig_openat_t)dlsym(RTLD_NEXT, "openat");
    pathname = redirect_path(pathname);
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode_t mode = va_arg(args, mode_t);
        va_end(args);
        return orig(dirfd, pathname, flags, mode);
    }
    return orig(dirfd, pathname, flags);
}

typedef int (*orig_openat64_t)(int dirfd, const char *pathname, int flags, ...);
int openat64(int dirfd, const char *pathname, int flags, ...) {
    orig_openat64_t orig = (orig_openat64_t)dlsym(RTLD_NEXT, "openat64");
    pathname = redirect_path(pathname);
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode_t mode = va_arg(args, mode_t);
        va_end(args);
        return orig(dirfd, pathname, flags, mode);
    }
    return orig(dirfd, pathname, flags);
}

typedef FILE *(*orig_fopen_t)(const char *pathname, const char *mode);
FILE *fopen(const char *pathname, const char *mode) {
    orig_fopen_t orig = (orig_fopen_t)dlsym(RTLD_NEXT, "fopen");
    pathname = redirect_path(pathname);
    return orig(pathname, mode);
}

typedef FILE *(*orig_fopen64_t)(const char *pathname, const char *mode);
FILE *fopen64(const char *pathname, const char *mode) {
    orig_fopen64_t orig = (orig_fopen64_t)dlsym(RTLD_NEXT, "fopen64");
    pathname = redirect_path(pathname);
    return orig(pathname, mode);
}
