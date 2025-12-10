<?php
declare(strict_types=1);

require_once __DIR__ . '/codec.php';

use function Adpcm\adpcm_encode;
use function Adpcm\adpcm_decode;
use function Adpcm\maximise_volume;
use function Adpcm\load_raw_pcm;
use function Adpcm\save_raw_pcm;
use function Adpcm\convert_to_mono_wav;

// Parse CLI options (mirroring the Python Argparse interface)
$short = "i:o:e:s:mrw";
$long  = [
    "input:",
    "output:",
    "encoded:",
    "samplingrate::",
    "maximise",
    "raw",
    "wav",
];

$options = getopt($short, $long);

$input  = $options['i'] ?? $options['input']  ?? null;
$output = $options['o'] ?? $options['output'] ?? null;
$encoded = $options['e'] ?? $options['encoded'] ?? null;

$samplingRate = 22050;
if (isset($options['s']) || isset($options['samplingrate'])) {
    $samplingRate = (int)($options['s'] ?? $options['samplingrate']);
}

$maximise = array_key_exists('m', $options) || array_key_exists('maximise', $options);
$raw      = array_key_exists('r', $options) || array_key_exists('raw', $options);
$wav      = array_key_exists('w', $options) || array_key_exists('wav', $options);

if ($input === null || $output === null || $encoded === null) {
    fwrite(STDERR,
        "Usage: php codecTest.php ".
        "-i INPUT -o OUTPUT.wav -e ENCODED.raw [-s RATE] [-m] [-r] [-w]\n"
    );
    exit(1);
}

if ($raw && $wav) {
    fwrite(STDERR, "Please specify only one of --raw or --wav\n");
    exit(1);
}

// Load / decode input
if ($wav) {
    // If input is WAV, normalise to mono first
    $tmp = sys_get_temp_dir() . DIRECTORY_SEPARATOR . "tmp_mono_" . uniqid() . ".wav";
    convert_to_mono_wav($input, $tmp, $samplingRate);
    $inputForRaw = $tmp;

    // Now read as 16-bit PCM
    // Use `sox`/ffmpeg to write raw if you want; here we keep it simple:
    // Call ffmpeg to dump to s16le raw and read it back.
    $rawPath = sys_get_temp_dir() . DIRECTORY_SEPARATOR . "tmp_raw_" . uniqid() . ".raw";
    $cmd = sprintf(
        'ffmpeg -y -i %s -f s16le -ac 1 -ar %d %s 2>&1',
        escapeshellarg($inputForRaw),
        $samplingRate,
        escapeshellarg($rawPath)
    );
    exec($cmd, $ffOut, $ffCode);
    if ($ffCode !== 0) {
        fwrite(STDERR, "ffmpeg failed while dumping raw PCM\n");
        exit(1);
    }
    $pcm = load_raw_pcm($rawPath);
    @unlink($tmp);
    @unlink($rawPath);
    echo "Loaded ".count($pcm)." PCM samples from WAV $input\n";

} else {
    // Input is raw or ADPCM bytes
    $data = file_get_contents($input);
    if ($data === false) {
        fwrite(STDERR, "Failed to read $input\n");
        exit(1);
    }

    if ($raw) {
        $pcm = load_raw_pcm($input);
        echo "Using ".count($pcm)." raw PCM samples\n";
    } else {
        echo "Decoding ADPCM from $input\n";
        $pcm = adpcm_decode($data);
        echo "Decoded ".count($pcm)." samples from ADPCM\n";
    }
}

// Maximise option
if ($maximise) {
    $pcm = maximise_volume($pcm);
    echo "Maximised volume\n";
}

// Encode to ADPCM
$adpcmBytes = adpcm_encode($pcm);
echo "Encoded ".strlen($adpcmBytes)." bytes to ADPCM\n";

// Save decoded PCM as WAV (using ffmpeg: s16le -> wav)
// First, save raw PCM
$tmpPcm = sys_get_temp_dir() . DIRECTORY_SEPARATOR . "tmp_pcm_" . uniqid() . ".raw";
save_raw_pcm($tmpPcm, $pcm);

// Now call ffmpeg to wrap to WAV with correct sample rate
$cmd = sprintf(
    'ffmpeg -y -f s16le -ac 1 -ar %d -i %s %s 2>&1',
    $samplingRate,
    escapeshellarg($tmpPcm),
    escapeshellarg($output)
);
exec($cmd, $ffOut, $ffCode);
@unlink($tmpPcm);
if ($ffCode !== 0) {
    fwrite(STDERR, "ffmpeg failed while writing WAV\n");
    exit(1);
}

// Save ADPCM as raw
file_put_contents($encoded, $adpcmBytes);

echo "Saved decoded PCM WAV to $output and encoded ADPCM to $encoded\n";
