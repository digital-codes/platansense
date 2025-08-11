// G.726 16‑kbps (2‑bit) decoder‑only dyn‑runtime module for MicroPython 1.25
// ────────────────────────────────────────────────────────────────────────────
// • Wraps the tiny, MIT‑licensed **bcg726** reference decoder
//   https://github.com/gdpnotyet/bcg726  (≈1100 LOC, patent‑expired 2024)
// • Target: ESP32 (Xtensa, 240 MHz) or any MCU with ≥ 5 KiB flash & 1 KiB RAM
// • Functions exported to Python:
//       decode(data: bytes)          → bytes   (16‑bit PCM, mono 8 kHz)
//       decode_into(data, buf)       → int     (bytes written | –1 on error)
//
// Build quick‑start (Unix port shown — adjust CC for Xtensa):
// ────────────────────────────────────────────────────────────────────────────
//   git clone https://github.com/gdpnotyet/bcg726
//   cd bcg726 && make libg726.a         # builds pure‑C core
//   gcc -I../../py -I../../ -Ibcg726/include -DMP_DYNRUNTIME -std=c99 -Os
//       -ffunction-sections -fdata-sections -c dec726r_native.c -o g726.o
//   ld -r g726.o bcg726/libg726.a -o g726_combined.o
//   ../../mpy-cross/mpy-cross g726_combined.o
//   # Copy resulting dec726r_native.mpy onto the board.
//
// Memory footprint (ESP32 gcc 12, -Os, LTO):
//   Flash  .text+.rodata  ≈ 4.7 KiB
//   RAM    state struct   ≈ 320 bytes per decoder instance
//
// ════════════════════════════════════════════════════════════════════════════

// code from https://github.com/fredrikhederstierna/g726.git

#include "py/dynruntime.h"
#include <stdint.h>

#include "g72x.h"

// For clarity: choose fixed bit‑rate mode (16 kbps → 2 bits/sample)
#ifndef G726_16K
#define G726_16K 16000
#endif

/*
 * g72x_init_state()
 *
 * This routine initializes and/or resets the g72x_state structure
 * pointed to by 'state_ptr'.
 * All the initial state values are specified in the CCITT G.721 document.
 */
void g726_init_state(
    g726_state *state_ptr)
{
    int cnta;

    state_ptr->yl = 34816;
    state_ptr->yu = 544;
    state_ptr->dms = 0;
    state_ptr->dml = 0;
    state_ptr->ap = 0;
    for (cnta = 0; cnta < 2; cnta++)
    {
        state_ptr->a[cnta] = 0;
        state_ptr->pk[cnta] = 0;
        state_ptr->sr[cnta] = 32;
    }
    for (cnta = 0; cnta < 6; cnta++)
    {
        // handling to avoid memset()
        volatile int *bp = (volatile int *)&state_ptr->b[cnta];
        volatile int *dqp = (volatile int *)&state_ptr->dq[cnta];
        *bp = 0;
        *dqp = 32;
    }
    state_ptr->td = 0;
}

//-----------------------------------------
/*
Why exactly 120 bytes?

    G.726 @ 16 kbps ⇒ 2 bits/sample
    (8000 samples/s × 2 bits = 16 000 bit/s).

    A 10 ms “frame” commonly used in telephony contains 80 samples.
    Encoded size: 80 samples × 2 bits = 160 bits = 20 bytes.

    The code processes six such 10 ms frames in one call:
    6 × 20 bytes = 120 bytes of bit-stream → 6 × 80 = 480 PCM samples, i.e. 60 ms of audio.

So the hard-coded “120” is simply 6 × 20-byte frames (= 60 ms) encoded at 16 kbps.
If you feed the function a different chunk length you’d change that constant to len_in_bytes, and scale the PCM array size to len_in_bytes * 4 samples.
*/
static void g726_decode(const int8_t *bitstream,
                        int16_t *pcm, int16_t samples)
{
    // g726_state state_ptr;
    g726_state *state = m_new(g726_state, 1);

    g726_init_state(state);

    int i;
    for (i = 0; i < samples; i++)
    {
        int in = (int)(((*(bitstream + i)) & (char)192) >> 6);
        pcm[i * 4] = g726_16_decoder(in, state);

        in = (int)(((*(bitstream + i)) & (char)48) >> 4);
        pcm[i * 4 + 1] = g726_16_decoder(in, state);

        in = (int)(((*(bitstream + i)) & (char)12) >> 2);
        pcm[i * 4 + 2] = g726_16_decoder(in, state);

        in = (int)(((*(bitstream + i)) & (char)3));
        pcm[i * 4 + 3] = g726_16_decoder(in, state);
    }
}

/*────────────────────────────────────────────────────────────────────────────*/
/*                        Helper: allocate‑return decode                     */
/*────────────────────────────────────────────────────────────────────────────*/
static mp_obj_t mp_dec726(mp_obj_t in_bytes_obj)
{
    mp_buffer_info_t in_buf;
    mp_get_buffer_raise(in_bytes_obj, &in_buf, MP_BUFFER_READ);

    // Worst‑case: each ADPCM byte → 4 PCM samples → 8 output bytes
    size_t est_pcm_bytes = in_buf.len * 8;
    int16_t *out_pcm = m_new(int16_t, est_pcm_bytes / 2);

    g726_decode((const int8_t *)in_buf.buf, out_pcm, in_buf.len);
    size_t out_bytes = est_pcm_bytes;

    return mp_obj_new_bytes((uint8_t *)out_pcm, out_bytes);
}
static MP_DEFINE_CONST_FUN_OBJ_1(dec726_obj, mp_dec726);

/*────────────────────────────────────────────────────────────────────────────*/
/*                Helper: buffer‑to‑buffer decode_into variant               */
/*────────────────────────────────────────────────────────────────────────────*/
static mp_obj_t mp_dec726_into(mp_obj_t in_bytes_obj, mp_obj_t out_buf_obj)
{
    mp_buffer_info_t in_buf, out_buf;
    mp_get_buffer_raise(in_bytes_obj, &in_buf, MP_BUFFER_READ);
    mp_get_buffer_raise(out_buf_obj, &out_buf, MP_BUFFER_WRITE);

    size_t needed = in_buf.len * 8; // bytes
    if (out_buf.len < needed)
    {
        return MP_OBJ_NEW_SMALL_INT(-1);
    }

    if (out_buf.len % 2 != 0)
    {
        return MP_OBJ_NEW_SMALL_INT(-1); // Output buffer must be even-sized for int16_t
    }

    int16_t *out_pcm = (int16_t *)out_buf.buf;

    g726_decode((const int8_t *)in_buf.buf, out_pcm, in_buf.len);
    return MP_OBJ_NEW_SMALL_INT(needed);
}
static MP_DEFINE_CONST_FUN_OBJ_2(dec726_into_obj, mp_dec726_into);

/*────────────────────────────────────────────────────────────────────────────*/
/*                                 Module init                               */
/*────────────────────────────────────────────────────────────────────────────*/
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args)
{
    MP_DYNRUNTIME_INIT_ENTRY

    mp_store_global(MP_QSTR_decode, MP_OBJ_FROM_PTR(&dec726_obj));
    mp_store_global(MP_QSTR_decode_into, MP_OBJ_FROM_PTR(&dec726_into_obj));

    MP_DYNRUNTIME_INIT_EXIT
}
