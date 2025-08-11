#ifndef _ADPCM_H_
#define _ADPCM_H_

#include <stdint.h>

// State for both encoder and decoder
typedef struct {
    int valprev;
    int index;
} adpcm_state_t;

void adpcm_encode(int16_t *pcm, uint8_t *adpcm, int nsamples, adpcm_state_t *state);
void adpcm_decode(uint8_t *adpcm, int16_t *pcm, int nsamples, adpcm_state_t *state);


#endif
