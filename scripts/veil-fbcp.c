/*
 * veil-fbcp - mirror the vc4 KMS framebuffer to the fbtft SPI panel.
 *
 * Route B for the 3.5" SPI panel (CE04868 / ILI9486 class): the kiosk renders
 * with hardware GL on the vc4 GPU, which can only scan out HDMI/DSI/DPI - never
 * SPI. This small daemon copies each rendered frame from the vc4 framebuffer
 * (/dev/fb0) to the SPI panel's fbtft framebuffer (/dev/fb1), converting the
 * pixel format as needed (e.g. 32bpp XRGB8888 -> 16bpp RGB565).
 *
 * It deliberately replaces fbcp-ili9341, which is built on the deprecated
 * DispmanX API and is 32-bit only - both unsupported on Raspberry Pi OS Trixie
 * 64-bit with the KMS display stack.
 *
 * The framebuffer geometry is re-read every frame so a mode change (e.g. Xorg
 * briefly selecting its fallback mode) neither reads out of bounds nor desyncs.
 *
 * Usage: veil-fbcp [src] [dst] [fps]
 *   src  default /dev/fb0
 *   dst  default /dev/fb1
 *   fps  default 25
 *
 * License: MIT.
 */

#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static void msleep(int ms) {
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (long)(ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
}

static unsigned umin(unsigned a, unsigned b) { return a < b ? a : b; }

/* Read one colour channel from a pixel buffer and scale it to 0..255. */
static unsigned get_channel(const unsigned char *p, int bpp, int off,
                            unsigned chan_off, unsigned chan_len) {
    unsigned v;
    if (bpp == 16)
        v = p[off] | (p[off + 1] << 8);
    else if (bpp == 32)
        v = p[off] | (p[off + 1] << 8) | (p[off + 2] << 16) | ((unsigned)p[off + 3] << 24);
    else
        v = p[off];
    if (chan_len == 0)
        return 0;
    unsigned c = (v >> chan_off) & ((1u << chan_len) - 1);
    if (chan_len == 8)
        return c;
    return (c * 255u) / ((1u << chan_len) - 1);
}

/* Write a 0..255 colour channel into a pixel buffer, scaling to chan_len. */
static void put_channel(unsigned char *p, int bpp, int off,
                        unsigned chan_off, unsigned chan_len, unsigned val8) {
    if (chan_len == 0)
        return;
    unsigned c = (chan_len == 8) ? val8 : (val8 * ((1u << chan_len) - 1)) / 255u;
    unsigned mask = ((1u << chan_len) - 1) << chan_off;
    if (bpp == 16) {
        unsigned v = p[off] | (p[off + 1] << 8);
        v = (v & ~mask) | (c << chan_off);
        p[off] = v & 0xff;
        p[off + 1] = (v >> 8) & 0xff;
    } else if (bpp == 32) {
        unsigned v = p[off] | (p[off + 1] << 8) | (p[off + 2] << 16) |
                     ((unsigned)p[off + 3] << 24);
        v = (v & ~mask) | (c << chan_off);
        p[off] = v & 0xff;
        p[off + 1] = (v >> 8) & 0xff;
        p[off + 2] = (v >> 16) & 0xff;
        p[off + 3] = (v >> 24) & 0xff;
    } else {
        p[off] = c & 0xff;
    }
}

struct fb {
    const char *path;
    int fd;
    int writable;
    struct fb_var_screeninfo var;
    struct fb_fix_screeninfo fix;
    unsigned char *mem;
    size_t len;
};

/* (Re)read geometry and grow the mapping if the framebuffer got larger. */
static int fb_sync(struct fb *f) {
    if (ioctl(f->fd, FBIOGET_VSCREENINFO, &f->var) < 0 ||
        ioctl(f->fd, FBIOGET_FSCREENINFO, &f->fix) < 0)
        return -1;
    size_t need = f->fix.smem_len
                      ? f->fix.smem_len
                      : (size_t)f->fix.line_length * f->var.yres_virtual;
    if (need > f->len) {
        if (f->mem && f->mem != MAP_FAILED)
            munmap(f->mem, f->len);
        f->len = need;
        f->mem = mmap(NULL, f->len,
                      f->writable ? (PROT_READ | PROT_WRITE) : PROT_READ,
                      MAP_SHARED, f->fd, 0);
        if (f->mem == MAP_FAILED) {
            fprintf(stderr, "veil-fbcp: mmap %s: %s\n", f->path, strerror(errno));
            f->mem = NULL;
            return -1;
        }
    }
    return 0;
}

static int fb_open(struct fb *f, const char *path, int writable) {
    memset(f, 0, sizeof(*f));
    f->path = path;
    f->writable = writable;
    f->fd = open(path, writable ? O_RDWR : O_RDONLY);
    if (f->fd < 0) {
        fprintf(stderr, "veil-fbcp: open %s: %s\n", path, strerror(errno));
        return -1;
    }
    if (fb_sync(f) < 0) {
        close(f->fd);
        f->fd = -1;
        return -1;
    }
    return 0;
}

static void fb_close(struct fb *f) {
    if (f->mem && f->mem != MAP_FAILED)
        munmap(f->mem, f->len);
    if (f->fd >= 0)
        close(f->fd);
}

int main(int argc, char **argv) {
    const char *src = argc > 1 ? argv[1] : "/dev/fb0";
    const char *dst = argc > 2 ? argv[2] : "/dev/fb1";
    int fps = argc > 3 ? atoi(argv[3]) : 25;
    if (fps < 1)
        fps = 1;

    struct fb s, d;
    if (fb_open(&s, src, 0) < 0)
        return 1;
    if (fb_open(&d, dst, 1) < 0) {
        fb_close(&s);
        return 1;
    }

    fprintf(stderr,
            "veil-fbcp: %s %ux%u@%dbpp -> %s %ux%u@%dbpp, %dfps\n",
            src, s.var.xres, s.var.yres, s.var.bits_per_pixel,
            dst, d.var.xres, d.var.yres, d.var.bits_per_pixel, fps);

    for (;;) {
        if (fb_sync(&s) < 0 || fb_sync(&d) < 0) {
            msleep(1000 / fps);
            continue;
        }
        int spv = s.var.bits_per_pixel / 8;
        int dpv = d.var.bits_per_pixel / 8;
        unsigned w = umin(s.var.xres, d.var.xres);
        unsigned h = umin(s.var.yres, d.var.yres);
        for (unsigned y = 0; y < h; y++) {
            const unsigned char *srow = s.mem + (size_t)y * s.fix.line_length;
            unsigned char *drow = d.mem + (size_t)y * d.fix.line_length;
            for (unsigned x = 0; x < w; x++) {
                const unsigned char *sp = srow + (size_t)x * spv;
                unsigned char *dp = drow + (size_t)x * dpv;
                unsigned r = get_channel(sp, s.var.bits_per_pixel, 0,
                                         s.var.red.offset, s.var.red.length);
                unsigned g = get_channel(sp, s.var.bits_per_pixel, 0,
                                         s.var.green.offset, s.var.green.length);
                unsigned b = get_channel(sp, s.var.bits_per_pixel, 0,
                                         s.var.blue.offset, s.var.blue.length);
                put_channel(dp, d.var.bits_per_pixel, 0,
                            d.var.red.offset, d.var.red.length, r);
                put_channel(dp, d.var.bits_per_pixel, 0,
                            d.var.green.offset, d.var.green.length, g);
                put_channel(dp, d.var.bits_per_pixel, 0,
                            d.var.blue.offset, d.var.blue.length, b);
            }
        }
        msleep(1000 / fps);
    }

    fb_close(&s);
    fb_close(&d);
    return 0;
}
