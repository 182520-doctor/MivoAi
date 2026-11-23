param(
    [string]$TextFile = "",
    [string]$OutputFile = "",
    [string]$VoiceName = "",
    [int]$Rate = 0,
    [switch]$ListVoices
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

if ($ListVoices) {
    $voices = @(
        $synth.GetInstalledVoices() | ForEach-Object {
            if ($_.Enabled) {
                [pscustomobject]@{
                    name = $_.VoiceInfo.Name
                    culture = $_.VoiceInfo.Culture.Name
                    gender = $_.VoiceInfo.Gender.ToString()
                }
            }
        }
    )
    $synth.Dispose()
    Write-Output ($voices | ConvertTo-Json -Compress)
    exit 0
}

if (-not $TextFile -or -not $OutputFile) {
    throw "TextFile and OutputFile are required"
}

$text = [System.IO.File]::ReadAllText(
    $TextFile,
    [System.Text.Encoding]::UTF8
)
if (-not $text.Trim()) {
    throw "Speech text cannot be empty"
}

if ($VoiceName) {
    $synth.SelectVoice($VoiceName)
}

$clampedRate = [Math]::Max(-10, [Math]::Min(10, $Rate))
$synth.Rate = $clampedRate
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    48000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono
)
$synth.SetOutputToWaveFile($OutputFile, $format)
$synth.Speak($text)
$synth.Dispose()
