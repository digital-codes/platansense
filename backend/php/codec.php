<?php
declare(strict_types=1);

namespace Adpcm;

const STEP_TABLE = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
];

const INDEX_TABLE = [
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8,
];

/**
 * @param int[] $pcmSamples int16 PCM samples
 * @return string           packed IMA ADPCM bytes
 */
function adpcm_encode(array $pcmSamples): string
{
    $index = 0;
    $valprev = 0;
    $step = STEP_TABLE[$index];

    $out = '';
    $toggle = false;
    $currentByte = 0;

    foreach ($pcmSamples as $i => $sample) {
        // Force into int16 range
        if ($sample < -32768) $sample = -32768;
        if ($sample >  32767) $sample =  32767;

        $diff = $sample - $valprev;
        $sign = 0;
        if ($diff < 0) {
            $sign = 8;
            $diff = -$diff;
        }

        $delta = 0;
        $tempstep = $step;

        if ($diff >= $tempstep) {
            $delta |= 4;
            $diff -= $tempstep;
        }
        $tempstep >>= 1;
        if ($diff >= $tempstep) {
            $delta |= 2;
            $diff -= $tempstep;
        }
        $tempstep >>= 1;
        if ($diff >= $tempstep) {
            $delta |= 1;
        }

        $delta |= $sign;

        // Update predicted value
        $vpdiff = $step >> 3;
        if ($delta & 4) $vpdiff += $step;
        if ($delta & 2) $vpdiff += ($step >> 1);
        if ($delta & 1) $vpdiff += ($step >> 2);

        if ($sign) {
            $valprev -= $vpdiff;
        } else {
            $valprev += $vpdiff;
        }

        if ($valprev < -32768) $valprev = -32768;
        if ($valprev >  32767) $valprev =  32767;

        // Update step index
        $index += INDEX_TABLE[$delta & 0x0F];
        if ($index < 0) $index = 0;
        if ($index > 88) $index = 88;
        $step = STEP_TABLE[$index];

        // Pack 2 nibbles per byte
        if ($toggle) {
            $currentByte |= ($delta & 0x0F);
            $out .= chr($currentByte);
            $toggle = false;
        } else {
            $currentByte = ($delta << 4) & 0xF0;
            $toggle = true;
        }
    }

    if ($toggle) {
        // We had a dangling high nibble
        $out .= chr($currentByte);
    }

    return $out;
}

/**
 * @param string $adpcmBytes raw IMA ADPCM
 * @return int[]             int16 PCM samples
 */
function adpcm_decode(string $adpcmBytes): array
{
    $len = strlen($adpcmBytes);
    $nsamples = $len * 2;
    $pcm = [];

    $index = 0;
    $valprev = 0;
    $step = STEP_TABLE[$index];

    for ($i = 0; $i < $len; $i++) {
        $byte = ord($adpcmBytes[$i]);

        // high nibble then low nibble, same as Python
        for ($shift = 4; $shift >= 0; $shift -= 4) {
            $delta = ($byte >> $shift) & 0x0F;

            $sign = $delta & 8;
            $delta &= 7;

            $vpdiff = $step >> 3;
            if ($delta & 4) $vpdiff += $step;
            if ($delta & 2) $vpdiff += ($step >> 1);
            if ($delta & 1) $vpdiff += ($step >> 2);

            if ($sign) {
                $valprev -= $vpdiff;
            } else {
                $valprev += $vpdiff;
            }

            if ($valprev < -32768) $valprev = -32768;
            if ($valprev >  32767) $valprev =  32767;

            $index += INDEX_TABLE[$delta];
            if ($index < 0) $index = 0;
            if ($index > 88) $index = 88;
            $step = STEP_TABLE[$index];

            $pcm[] = $valprev;
        }
    }

    return $pcm;
}

/**
 * Maximise volume of int16 PCM with some headroom.
 *
 * @param int[] $pcm
 * @param float $headroom
 * @return int[]
 */
function maximise_volume(array $pcm, float $headroom = 0.002): array
{
    if (empty($pcm)) {
        return $pcm;
    }

    $maxAbs = 0;
    foreach ($pcm as $v) {
        $abs = abs($v);
        if ($abs > $maxAbs) {
            $maxAbs = $abs;
        }
    }

    if ($maxAbs === 0) {
        return $pcm;
    }

    $scale = (1.0 - $headroom) * 32767.0 / $maxAbs;

    $out = [];
    foreach ($pcm as $v) {
        $scaled = (int) round($v * $scale);
        if ($scaled < -32768) $scaled = -32768;
        if ($scaled >  32767) $scaled =  32767;
        $out[] = $scaled;
    }

    return $out;
}

/**
 * Helper: load int16 little-endian PCM from a raw file.
 *
 * @return int[]
 */
function load_raw_pcm(string $path): array
{
    $data = file_get_contents($path);
    if ($data === false) {
        throw new \RuntimeException("Failed to read $path");
    }

    $len = strlen($data);
    if ($len % 2 !== 0) {
        throw new \RuntimeException("Raw PCM must have even length (16-bit samples)");
    }

    $samples = [];
    for ($i = 0; $i < $len; $i += 2) {
        $lo = ord($data[$i]);
        $hi = ord($data[$i + 1]);
        $val = $lo | ($hi << 8);
        if ($val & 0x8000) {
            $val -= 0x10000; // sign-extend
        }
        $samples[] = $val;
    }
    return $samples;
}

/**
 * Helper: write int16 PCM to little-endian raw file.
 *
 * @param int[] $pcm
 */
function save_raw_pcm(string $path, array $pcm): void
{
    $bin = '';
    foreach ($pcm as $v) {
        if ($v < 0) {
            $v += 0x10000;
        }
        $bin .= chr($v & 0xFF) . chr(($v >> 8) & 0xFF);
    }
    file_put_contents($path, $bin);
}

/**
 * Convert an arbitrary WAV (any channels/rate) to mono, 8 kHz WAV using ffmpeg.
 *
 * ffmpeg must be installed and in $PATH.
 */
/* call like so:
convert_to_mono_wav($input, $output, 8000);
*/
function convert_to_mono_wav(string $input, string $output, int $rate): void
{
    $cmd = sprintf(
        'ffmpeg -y -i %s -ac 1 -ar %d %s 2>&1',
        escapeshellarg($input),
        $rate, 
        escapeshellarg($output)
    );

    exec($cmd, $outLines, $exitCode);
    if ($exitCode !== 0) {
        throw new \RuntimeException(
            "ffmpeg failed (exit $exitCode):\n" . implode("\n", $outLines)
        );
    }
}
