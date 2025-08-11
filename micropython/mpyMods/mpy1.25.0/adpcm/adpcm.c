// Native dynruntime version of the ADPCM codec for MicroPython 1.25
// Converted from external cmodule to dynruntime native extension.
// Generated 2025-08-04.

#include "py/dynruntime.h"
#include <stdint.h>

static const int step_table[89] = {
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
};

static const int index_table[16] = {
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8
};

typedef struct {
    int valprev;
    int index;
} adpcm_state_t;

/* -------------------------------------------------------------------------- */
/*                        Core codec implementation                            */
/* -------------------------------------------------------------------------- */

/* 16‑bit PCM → 4‑bit ADPCM */
static void adpcm_encode(const int16_t *pcm, uint8_t *adpcm, int nsamples, adpcm_state_t *state) {
    int valprev = state->valprev;
    int index   = state->index;
    int step    = step_table[index];

    uint8_t hi_nibble = 0;
    int     toggle    = 0;        // 0 → write high nibble next, 1 → write low nibble next

    for (int i = 0; i < nsamples; ++i) {
        int diff  = pcm[i] - valprev;
        int sign  = (diff < 0) ? 8 : 0;
        if (sign) diff = -diff;

        int delta     = 0;
        int temp_step = step;
        if (diff >= temp_step) { delta |= 4; diff -= temp_step; }
        temp_step >>= 1;
        if (diff >= temp_step) { delta |= 2; diff -= temp_step; }
        temp_step >>= 1;
        if (diff >= temp_step) { delta |= 1; }
        delta |= sign;

        /* reconstruct */
        int vpdiff = step >> 3;
        if (delta & 4) vpdiff += step;
        if (delta & 2) vpdiff += step >> 1;
        if (delta & 1) vpdiff += step >> 2;
        if (sign) valprev -= vpdiff; else valprev += vpdiff;
        if (valprev < -32768) valprev = -32768;
        else if (valprev > 32767) valprev = 32767;

        index += index_table[delta & 0x0F];
        if (index < 0) index = 0; else if (index > 88) index = 88;
        step = step_table[index];

        /* pack nibbles */
        if (!toggle) {
            hi_nibble = (delta << 4) & 0xF0;
            toggle = 1;
        } else {
            *adpcm++ = hi_nibble | (delta & 0x0F);
            toggle = 0;
        }
    }

    state->valprev = valprev;
    state->index   = index;
}

/* 4‑bit ADPCM → 16‑bit PCM */
static void adpcm_decode(const uint8_t *adpcm, int16_t *pcm, int nsamples, adpcm_state_t *state) {
    int valprev = state->valprev;
    int index   = state->index;
    int step    = step_table[index];

    for (int i = 0; i < nsamples; ++i) {
        uint8_t packed = adpcm[i >> 1];
        int delta = (i & 1) ? (packed & 0x0F) : (packed >> 4);
        int sign  = delta & 8;
        delta    &= 7;

        int vpdiff = step >> 3;
        if (delta & 4) vpdiff += step;
        if (delta & 2) vpdiff += step >> 1;
        if (delta & 1) vpdiff += step >> 2;
        if (sign) valprev -= vpdiff; else valprev += vpdiff;
        if (valprev < -32768) valprev = -32768;
        else if (valprev > 32767) valprev = 32767;

        index += index_table[delta | sign];
        if (index < 0) index = 0; else if (index > 88) index = 88;
        step = step_table[index];

        pcm[i] = valprev;
    }

    state->valprev = valprev;
    state->index   = index;
}

/* -------------------------------------------------------------------------- */
/*                           Python‑visible helpers                            */
/* -------------------------------------------------------------------------- */

/* allocate‑return helpers --------------------------------------------------- */

static mp_obj_t py_adpcm_encode(mp_obj_t pcm_obj) {
    mp_buffer_info_t pcm_buf;
    mp_get_buffer_raise(pcm_obj, &pcm_buf, MP_BUFFER_READ);
    if (pcm_buf.len & 1) {
        mp_raise_ValueError(MP_ERROR_TEXT("PCM length must be even (16‑bit)"));
    }
    int nsamples = pcm_buf.len / 2;
    uint8_t *out = m_new(uint8_t, nsamples / 2);
    adpcm_state_t st = {0};
    adpcm_encode((const int16_t *)pcm_buf.buf, out, nsamples, &st);
    return mp_obj_new_bytes(out, nsamples / 2);
}
static MP_DEFINE_CONST_FUN_OBJ_1(adpcm_encode_obj, py_adpcm_encode);

static mp_obj_t py_adpcm_decode(mp_obj_t adpcm_obj) {
    mp_buffer_info_t adpcm_buf;
    mp_get_buffer_raise(adpcm_obj, &adpcm_buf, MP_BUFFER_READ);
    int nsamples  = adpcm_buf.len * 2;          // 2 samples per byte
    int16_t *pcm  = m_new(int16_t, nsamples);
    adpcm_state_t st = {0};
    adpcm_decode((const uint8_t *)adpcm_buf.buf, pcm, nsamples, &st);
    return mp_obj_new_bytes((uint8_t *)pcm, nsamples * 2);
}
static MP_DEFINE_CONST_FUN_OBJ_1(adpcm_decode_obj, py_adpcm_decode);

/* in‑place/buffer‑to‑buffer helpers ----------------------------------------- */
/* These return the encoded/decoded length or ‑1 on size mismatch. */

static mp_obj_t py_adpcm_encode_into(mp_obj_t pcm_obj, mp_obj_t out_obj) {
    mp_buffer_info_t pcm_buf, out_buf;
    mp_get_buffer_raise(pcm_obj, &pcm_buf, MP_BUFFER_READ);
    mp_get_buffer_raise(out_obj, &out_buf, MP_BUFFER_WRITE);

    if (pcm_buf.len & 1) {
        return MP_OBJ_NEW_SMALL_INT(-1);       // odd number of bytes
    }
    int nsamples      = pcm_buf.len / 2;
    int needed_bytes  = nsamples / 2;          // 2 samples ➔ 1 byte
    if (out_buf.len < needed_bytes) {
        return MP_OBJ_NEW_SMALL_INT(-1);
    }

    adpcm_state_t st = {0};
    adpcm_encode((const int16_t *)pcm_buf.buf, (uint8_t *)out_buf.buf, nsamples, &st);
    return MP_OBJ_NEW_SMALL_INT(needed_bytes);
}
static MP_DEFINE_CONST_FUN_OBJ_2(adpcm_encode_into_obj, py_adpcm_encode_into);

static mp_obj_t py_adpcm_decode_into(mp_obj_t adpcm_obj, mp_obj_t out_obj) {
    mp_buffer_info_t adpcm_buf, out_buf;
    mp_get_buffer_raise(adpcm_obj, &adpcm_buf, MP_BUFFER_READ);
    mp_get_buffer_raise(out_obj, &out_buf, MP_BUFFER_WRITE);

    int nsamples      = adpcm_buf.len * 2;
    int needed_bytes  = nsamples * 2;          // 16‑bit samples
    if (out_buf.len < needed_bytes) {
        return MP_OBJ_NEW_SMALL_INT(-1);
    }

    adpcm_state_t st = {0};
    adpcm_decode((const uint8_t *)adpcm_buf.buf, (int16_t *)out_buf.buf, nsamples, &st);
    return MP_OBJ_NEW_SMALL_INT(needed_bytes);
}
static MP_DEFINE_CONST_FUN_OBJ_2(adpcm_decode_into_obj, py_adpcm_decode_into);

/* -------------------------------------------------------------------------- */
/*                                Module init                                 */
/* -------------------------------------------------------------------------- */

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY

    mp_store_global(MP_QSTR_encode, MP_OBJ_FROM_PTR(&adpcm_encode_obj));
    mp_store_global(MP_QSTR_decode, MP_OBJ_FROM_PTR(&adpcm_decode_obj));
    mp_store_global(MP_QSTR_encode_into, MP_OBJ_FROM_PTR(&adpcm_encode_into_obj));
    mp_store_global(MP_QSTR_decode_into, MP_OBJ_FROM_PTR(&adpcm_decode_into_obj));

    MP_DYNRUNTIME_INIT_EXIT
}
