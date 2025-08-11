#include "py/obj.h"
#include "py/runtime.h"

#include <stdint.h>
#include "adpcm.h"

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

static mp_obj_t mod_adpcm_encode(mp_obj_t pcm_obj) {
    mp_buffer_info_t pcm_buf;
    mp_get_buffer_raise(pcm_obj, &pcm_buf, MP_BUFFER_READ);

    if (pcm_buf.len % 2 != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("PCM length must be even (16-bit samples)"));
    }

    int nsamples = pcm_buf.len / 2;
    uint8_t *out = m_new(uint8_t, nsamples / 2);
    adpcm_state_t state = {0};

    adpcm_encode((int16_t *)pcm_buf.buf, out, nsamples, &state);
    return mp_obj_new_bytes(out, nsamples / 2);
}
static MP_DEFINE_CONST_FUN_OBJ_1(mod_adpcm_encode_obj, mod_adpcm_encode);


static mp_obj_t mod_adpcm_decode(mp_obj_t adpcm_obj) {
    mp_buffer_info_t adpcm_buf;
    mp_get_buffer_raise(adpcm_obj, &adpcm_buf, MP_BUFFER_READ);

    int nsamples = adpcm_buf.len * 2;
    int16_t *pcm_out = m_new(int16_t, nsamples);
    adpcm_state_t state = {0};

    adpcm_decode((uint8_t *)adpcm_buf.buf, pcm_out, nsamples, &state);
    return mp_obj_new_bytes((uint8_t *)pcm_out, nsamples * 2);
}
static MP_DEFINE_CONST_FUN_OBJ_1(mod_adpcm_decode_obj, mod_adpcm_decode);


// 16-bit PCM to 4-bit ADPCM
void adpcm_encode(int16_t *pcm, uint8_t *adpcm, int nsamples, adpcm_state_t *state) {
    int valprev = state->valprev;
    int index = state->index;
    int step = step_table[index];
    uint8_t out = 0;
    int buffer = 0;

    for (int i = 0; i < nsamples; i++) {
        int diff = pcm[i] - valprev;
        int sign = (diff < 0) ? 8 : 0;
        if (sign) diff = -diff;

        int delta = 0;
        int tempstep = step;

        if (diff >= tempstep) { delta |= 4; diff -= tempstep; }
        tempstep >>= 1;
        if (diff >= tempstep) { delta |= 2; diff -= tempstep; }
        tempstep >>= 1;
        if (diff >= tempstep) delta |= 1;

        delta |= sign;

        int vpdiff = step >> 3;
        if (delta & 4) vpdiff += step;
        if (delta & 2) vpdiff += step >> 1;
        if (delta & 1) vpdiff += step >> 2;

        if (sign) valprev -= vpdiff;
        else      valprev += vpdiff;

        if (valprev > 32767) valprev = 32767;
        else if (valprev < -32768) valprev = -32768;

        index += index_table[delta];
        if (index < 0) index = 0;
        else if (index > 88) index = 88;

        step = step_table[index];

        if (buffer) {
            *adpcm++ = (out | (delta & 0x0F));
        } else {
            out = (delta << 4) & 0xF0;
        }
        buffer = !buffer;
    }

    state->valprev = valprev;
    state->index = index;
}

// 4-bit ADPCM to 16-bit PCM
void adpcm_decode(uint8_t *adpcm, int16_t *pcm, int nsamples, adpcm_state_t *state) {
    int valprev = state->valprev;
    int index = state->index;
    int step = step_table[index];

    for (int i = 0; i < nsamples; i++) {
        int delta = (i & 1) ? (adpcm[i >> 1] & 0x0F) : (adpcm[i >> 1] >> 4);
        int sign = delta & 8;
        delta &= 7;

        int vpdiff = step >> 3;
        if (delta & 4) vpdiff += step;
        if (delta & 2) vpdiff += step >> 1;
        if (delta & 1) vpdiff += step >> 2;

        if (sign) valprev -= vpdiff;
        else      valprev += vpdiff;

        if (valprev > 32767) valprev = 32767;
        else if (valprev < -32768) valprev = -32768;

        index += index_table[delta | sign];
        if (index < 0) index = 0;
        else if (index > 88) index = 88;

        step = step_table[index];

        pcm[i] = valprev;
    }

    state->valprev = valprev;
    state->index = index;
}

static const mp_rom_map_elem_t adpcm_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_encode), MP_ROM_PTR(&mod_adpcm_encode_obj) },
    { MP_ROM_QSTR(MP_QSTR_decode), MP_ROM_PTR(&mod_adpcm_decode_obj) },
};
static MP_DEFINE_CONST_DICT(adpcm_module_globals, adpcm_module_globals_table);

const mp_obj_module_t mp_module_adpcm = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&adpcm_module_globals,
};
MP_REGISTER_MODULE(MP_QSTR_adpcm, mp_module_adpcm);

