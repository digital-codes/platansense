<?php
/**
 * convert_to_adpcm.php - Convert WAV files to ADPCM for sensor testing
 * Uses the codec.php functions to encode audio in ADPCM format
 */

require_once __DIR__ . '/codec.php';
use function Adpcm\adpcm_encode;

function loadWavToPcm($wavFile) {
    /**
     * Load a WAV file and extract raw PCM data
     * 
     * @param string $wavFile Path to WAV file
     * @return array|int[] PCM samples as array of int16 values
     */
    if (!file_exists($wavFile)) {
        throw new Exception("WAV file not found: $wavFile");
    }
    
    $wavData = file_get_contents($wavFile);
    if ($wavData === false) {
        throw new Exception("Failed to read WAV file: $wavFile");
    }
    
    // Check WAV format
    if (strlen($wavData) < 44) {
        throw new Exception("WAV file too small, invalid format");
    }
    
    // Check RIFF header
    if (substr($wavData, 0, 4) !== 'RIFF') {
        throw new Exception("Invalid WAV file: missing RIFF header");
    }
    
    // Check WAVE format
    if (substr($wavData, 8, 4) !== 'WAVE') {
        throw new Exception("Invalid WAV file: missing WAVE header");
    }
    
    // Parse WAV header to get PCM data position
    // WAV header structure:
    // RIFF(4) + chunk_size(4) + WAVE(4) + fmt(4) + fmt_size(4) +
    // audio_format(2) + channels(2) + sample_rate(4) + byte_rate(4) +
    // block_align(2) + bits_per_sample(2) + data(4) + data_size(4) = 44 bytes
    
    $fmt_chunk = substr($wavData, 12, 8);
    $audio_format = unpack('v', substr($fmt_chunk, 0, 2))[1];
    $channels = unpack('v', substr($fmt_chunk, 2, 2))[1];
    $sample_rate = unpack('V', substr($fmt_data = substr($wavData, 20, 4))[1])[1];
    $bits_per_sample = unpack('v', substr($fmt_chunk, 14, 2))[1];
    
    // Validate format
    if ($audio_format !== 1) {
        throw new Exception("Unsupported audio format: $audio_format (expected PCM=1)");
    }
    
    if ($channels !== 1) {
        throw new Exception("Only mono audio is supported");
    }
    
    if ($sample_rate !== 8000) {
        echo "Warning: Sample rate is $sample_rate Hz (expected 8000 Hz)\n";
    }
    
    if ($bits_per_sample !== 16) {
        throw new Exception("Only 16-bit audio is supported");
    }
    
    // Find data chunk
    $data_pos = strpos($wavData, 'data', 12);
    if ($data_pos === false) {
        throw new Exception("Data chunk not found in WAV file");
    }
    
    // Skip data chunk header (4 bytes for 'data' + 4 bytes for size)
    $pcm_start = $data_pos + 8;
    
    // Extract PCM data
    $pcmData = substr($wavData, $pcm_start);
    
    // Convert to array of int16 values
    $samples = [];
    $sample_count = strlen($pcmData) / 2;
    
    for ($i = 0; $i < $sample_count; $i++) {
        $offset = $i * 2;
        // Little-endian 16-bit
        $sample = unpack('v', substr($pcmData, $offset, 2))[1];
        
        // Convert to signed 16-bit
        if ($sample & 0x8000) {
            $sample -= 0x10000;
        }
        
        $samples[] = $sample;
    }
    
    return [
        'samples' => $samples,
        'sample_rate' => $sample_rate,
        'channels' => $channels,
        'bits_per_sample' => $bits_per_sample,
        'sample_count' => $sample_count,
        'duration' => $sample_count / $sample_rate
    ];
}

function convertPcmToAdpcm($pcmSamples) {
    /**
     * Convert PCM samples to ADPCM encoded data
     * 
     * @param array|int[] $pcmSamples Array of int16 PCM samples
     * @return string ADPCM encoded bytes
     */
    if (empty($pcmSamples)) {
        throw new Exception("No PCM samples to encode");
    }
    
    return adpcm_encode($pcmSamples);
}

function saveAdpcmFile($adpcmData, $outputFile) {
    /**
     * Save ADPCM data to file
     * 
     * @param string $adpcmData ADPCM encoded bytes
     * @param string $outputFile Output file path
     */
    $result = file_put_contents($outputFile, $adpcmData);
    if ($result === false) {
        throw new Exception("Failed to write ADPCM file: $outputFile");
    }
    
    return $result;
}

function create_metadata_json($metadata, $outputFile) {
    /**
     * Create JSON metadata file
     * 
     * @param array $metadata Metadata array
     * @param string $outputFile Output file path
     */
    $json = json_encode($metadata, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    $result = file_put_contents($outputFile, $json);
    if ($result === false) {
        throw new Exception("Failed to write metadata file: $outputFile");
    }
    
    return $result;
}

// Main CLI interface
if (php_sapi_name() === 'cli') {
    $options = getopt('i:o:d:m::h', ['input:', 'output:', 'dir:', 'metadata::', 'help']);
    
    if (isset($options['h']) || isset($options['help'])) {
        echo "Usage: php convert_to_adpcm.php [OPTIONS]\n\n";
        echo "Options:\n";
        echo "  -i <file>     Input WAV file\n";
        echo "  -o <file>     Output ADPCM file\n";
        echo "  -d <dir>      Process all WAV files in directory\n";
        echo "  -m <file>     Create metadata file (optional)\n";
        echo "  -h, --help    Show this help\n\n";
        echo "Examples:\n";
        echo "  php convert_to_adpcm.php -i input.wav -o output.adpcm\n";
        echo "  php convert_to_adpcm.php -d ./wav_samples/ -m metadata.json\n";
        exit(0);
    }
    
    // Single file mode
    if (isset($options['i'])) {
        $inputFile = $options['i'];
        $outputFile = isset($options['o']) ? $options['o'] : preg_replace('/\.wav$/i', '.adpcm', $inputFile);
        
        echo "Converting WAV to ADPCM:\n";
        echo "  Input:  $inputFile\n";
        echo "  Output: $outputFile\n";
        echo "  Processing...\n";
        
        try {
            // Load WAV file
            $pcmInfo = loadWavToPcm($inputFile);
            echo "  ✓ Loaded WAV: {$pcmInfo['sample_count']} samples, {$pcmInfo['duration']:.2f}s\n";
            
            // Convert to ADPCM
            $adpcmData = convertPcmToAdpcm($pcmInfo['samples']);
            echo "  ✓ Encoded to ADPCM: " . strlen($adpcmData) . " bytes\n";
            
            // Calculate compression ratio
            $originalSize = $pcmInfo['sample_count'] * 2; // 16-bit samples
            $compressionRatio = $originalSize / strlen($adpcmData);
            echo "  ✓ Compression ratio: " . number_format($compressionRatio, 2) . ":1\n";
            
            // Save ADPCM file
            saveAdpcmFile($adpcmData, $outputFile);
            echo "  ✓ Saved ADPCM file\n";
            
            echo "\n✓ Conversion successful!\n";
            exit(0);
            
        } catch (Exception $e) {
            echo "\n✗ Error: " . $e->getMessage() . "\n";
            exit(1);
        }
    }
    
    // Directory mode
    if (isset($options['d'])) {
        $inputDir = $options['d'];
        $metadataFile = isset($options['m']) ? $options['m'] : null;
        
        if (!is_dir($inputDir)) {
            echo "Error: Directory not found: $inputDir\n";
            exit(1);
        }
        
        echo "Processing WAV files in: $inputDir\n";
        echo "Output directory: ./adpcm_samples/\n";
        
        // Create output directory
        $outputDir = './adpcm_samples/';
        if (!is_dir($outputDir)) {
            mkdir($outputDir, 0755, true);
        }
        
        // Process all WAV files
        $wavFiles = glob($inputDir . '/*.wav');
        if (empty($wavFiles)) {
            echo "No WAV files found in: $inputDir\n";
            exit(0);
        }
        
        echo "Found " . count($wavFiles) . " WAV files\n";
        echo "Processing...\n\n";
        
        $results = [];
        $successCount = 0;
        
        foreach ($wavFiles as $wavFile) {
            $basename = basename($wavFile, '.wav');
            $adpcmFile = $outputDir . $basename . '.adpcm';
            
            echo "  Processing: $basename.wav... ";
            
            try {
                // Load WAV file
                $pcmInfo = loadWavToPcm($wavFile);
                
                // Convert to ADPCM
                $adpcmData = convertPcmToAdpcm($pcmInfo['samples']);
                
                // Save ADPCM file
                saveAdpcmFile($adpcmData, $adpcmFile);
                
                $originalSize = $pcmInfo['sample_count'] * 2;
                $compressionRatio = $originalSize / strlen($adpcmData);
                
                echo "✓ (" . number_format($compressionRatio, 1) . ":1, " . strlen($adpcmData) . " bytes)\n";
                
                $results[] = [
                    'input' => basename($wavFile),
                    'output' => basename($adpcmFile),
                    'original_size' => $originalSize,
                    'compressed_size' => strlen($adpcmData),
                    'compression_ratio' => round($compressionRatio, 2),
                    'duration' => round($pcmInfo['duration'], 2),
                    'sample_count' => $pcmInfo['sample_count']
                ];
                
                $successCount++;
                
            } catch (Exception $e) {
                echo "✗ (" . $e->getMessage() . ")\n";
            }
        }
        
        echo "\n✓ Successfully converted $successCount/" . count($wavFiles) . " files\n";
        
        // Create metadata if requested
        if ($metadataFile) {
            $metadata = [
                'description' => 'ADPCM audio files converted from WAV using codec.php',
                'codec' => 'IMA ADPCM',
                'input_directory' => $inputDir,
                'output_directory' => $outputDir,
                'total_files' => $successCount,
                'files' => $results
            ];
            
            create_metadata_json($metadata, $metadataFile);
            echo "✓ Metadata saved to: $metadataFile\n";
        }
        
        exit(0);
    }
    
    // No valid options
    echo "Usage: php convert_to_adpcm.php -i <input.wav> -o <output.adpcm>\n";
    echo "       php convert_to_adpcm.php -d <input_dir> -m <metadata.json>\n";
    echo "       php convert_to_adpcm.php -h\n";
    exit(1);
}
?>