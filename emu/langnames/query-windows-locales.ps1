<#
Ask Windows what NVDA asks it, for a list of locale names, and print the answers as JSON. Read-only: nothing on the box is changed.

NVDA's languageHandler.getLanguageDescription (source/languageHandler.py) takes a language's spoken name from three calls, and so does this script:
  1. LocaleNameToLCID(name, 0)   (LOCALE_CUSTOM_UNSPECIFIED, 0x1000, counts as "Windows does not know it")
  2. GetLocaleInfoW(lcid, LOCALE_SLANGDISPLAYNAME = 0x6f)   for a bare language
  3. GetLocaleInfoW(lcid, LOCALE_SLANGUAGE = 0x2)           for a language with a region, or when 2 returns 0
Both strings are recorded with their return values, whichever NVDA would have used, so the table can say which it took.

It also lists the speech voices the box has, because NVDA's "(not supported)" is the synthesizer's own answer: languageIsSupported(lang) is true
when a voice's language is `lang` or starts with it (synthDriverHandler.py:329). The voices come from Windows.Media.SpeechSynthesis, which is what
NVDA's OneCore synthesizer lists, and from the OneCore and SAPI 5 registry tokens beside it.

    query-windows-locales.ps1 -Worker a11y-worker-2 -Codes cy,en,az

Run as the worker's own account, as NVDA runs: SLANGDISPLAYNAME is in that account's UI language, which is recorded. Non-ASCII characters in the output
are written as \uXXXX so that no console or transport encoding can change them.
#>
param(
    [Parameter(Mandatory = $true)][string]$Worker,
    [Parameter(Mandatory = $true)][string[]]$Codes
)
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class NvdaLocaleCalls {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    public static extern int LocaleNameToLCID(string lpName, uint dwFlags);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, EntryPoint = "GetLocaleInfoW")]
    public static extern int GetLocaleInfo(int Locale, int LCType, StringBuilder lpLCData, int cchData);
}
'@

$LOCALE_SLANGUAGE = 0x2
$LOCALE_SLANGDISPLAYNAME = 0x6f
$LOCALE_CUSTOM_UNSPECIFIED = 0x1000

function Get-LocaleString([int]$Lcid, [int]$Type) {
    $buf = New-Object System.Text.StringBuilder 1024
    $res = [NvdaLocaleCalls]::GetLocaleInfo($Lcid, $Type, $buf, 1024)
    [ordered]@{ result = $res; value = $buf.ToString() }
}

$names = [ordered]@{}
foreach ($code in (($Codes -join ',') -split ',' | Where-Object { $_ -ne '' } | Sort-Object -Unique)) {
    $lcid = [NvdaLocaleCalls]::LocaleNameToLCID($code, 0)
    $entry = [ordered]@{ lcid = $lcid }
    if ($lcid -ne 0 -and $lcid -ne $LOCALE_CUSTOM_UNSPECIFIED) {
        $entry.displayName = Get-LocaleString $lcid $LOCALE_SLANGDISPLAYNAME
        $entry.language = Get-LocaleString $lcid $LOCALE_SLANGUAGE
    }
    $names[$code] = $entry
}

$voices = @()
$voiceError = $null
try {
    [void][Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
    foreach ($v in [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices) {
        $voices += [ordered]@{ language = $v.Language; displayName = $v.DisplayName; id = $v.Id }
    }
    $defaultVoice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::DefaultVoice
    $default = [ordered]@{ language = $defaultVoice.Language; displayName = $defaultVoice.DisplayName }
} catch {
    $voiceError = $_.Exception.Message
    $default = $null
}
$tokens = @()
foreach ($root in 'HKLM:\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens', 'HKLM:\SOFTWARE\Microsoft\Speech\Voices\Tokens') {
    if (Test-Path $root) {
        foreach ($t in Get-ChildItem $root) {
            $attr = Join-Path $t.PSPath 'Attributes'
            $lang = if (Test-Path $attr) { (Get-ItemProperty $attr).Language } else { $null }
            $tokens += [ordered]@{ store = ($root -replace '^HKLM:\\SOFTWARE\\Microsoft\\', ''); token = $t.PSChildName; language = $lang }
        }
    }
}

$os = Get-CimInstance Win32_OperatingSystem
$current = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$result = [ordered]@{
    worker = $Worker
    windows = [ordered]@{
        caption = $os.Caption
        build = "$($current.CurrentBuild).$($current.UBR)"
        uiCulture = (Get-UICulture).Name
        culture = (Get-Culture).Name
    }
    names = $names
    voices = [ordered]@{ winrt = $voices; winrtDefault = $default; winrtError = $voiceError; registryTokens = $tokens }
}
$json = $result | ConvertTo-Json -Depth 8 -Compress
$sb = New-Object System.Text.StringBuilder
foreach ($ch in $json.ToCharArray()) {
    if ([int]$ch -gt 126) { [void]$sb.AppendFormat('\u{0:x4}', [int]$ch) } else { [void]$sb.Append($ch) }
}
$sb.ToString()
