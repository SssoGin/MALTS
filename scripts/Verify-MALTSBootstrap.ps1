[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $ArchivePath,

    [string] $TransportManifestPath,
    [string] $ChecksumPath,
    [string] $ReleaseNotesPath,
    [string] $ExtractOutput,
    [switch] $Apply
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:BootstrapVersion = '1.0.0'
$script:BootstrapTag = 'v1.0.0'
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:ReservedNames = @('CON', 'PRN', 'AUX', 'NUL') + (1..9 | ForEach-Object { "COM$_" }) + (1..9 | ForEach-Object { "LPT$_" })

function Fail-Bootstrap {
    param([string] $Code, [string] $Message, [string] $Path)
    $suffix = if ([string]::IsNullOrWhiteSpace($Path)) { '' } else { " [$Path]" }
    throw "[$Code] $Message$suffix"
}

function Get-FullPath {
    param([string] $Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        Fail-Bootstrap 'MBV_PATH' 'A required path is empty.' $Path
    }
    return [System.IO.Path]::GetFullPath($Path)
}

function Get-Sha256Bytes {
    param([byte[]] $Bytes)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($algorithm.ComputeHash($Bytes))).Replace('-', '').ToUpperInvariant()
    }
    finally {
        $algorithm.Dispose()
    }
}

function Get-Sha256File {
    param([string] $Path)
    $stream = [System.IO.File]::OpenRead($Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToUpperInvariant()
    }
    finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}

function Assert-ExactProperties {
    param($Value, [string[]] $Expected, [string] $Context)
    if ($null -eq $Value) {
        Fail-Bootstrap 'MBV_MANIFEST_SHAPE' 'Required JSON object is null.' $Context
    }
    $actual = @($Value.PSObject.Properties | ForEach-Object { $_.Name } | Sort-Object)
    $wanted = @($Expected | Sort-Object)
    if (($actual -join "`n") -cne ($wanted -join "`n")) {
        Fail-Bootstrap 'MBV_MANIFEST_SHAPE' "Unexpected properties. Expected: $($wanted -join ', '); actual: $($actual -join ', ')." $Context
    }
}

function Assert-Sha256 {
    param([string] $Value, [string] $Context)
    if ($Value -cnotmatch '^[A-F0-9]{64}$') {
        Fail-Bootstrap 'MBV_SHA256' 'Expected an uppercase SHA-256 value.' $Context
    }
}

function Read-U16 {
    param([byte[]] $Bytes, [long] $Offset, [string] $Context)
    if ($Offset -lt 0 -or $Offset + 2 -gt $Bytes.LongLength) {
        Fail-Bootstrap 'MBV_ZIP_BOUNDS' 'ZIP structure exceeds archive bounds.' $Context
    }
    return [System.BitConverter]::ToUInt16($Bytes, [int] $Offset)
}

function Read-U32 {
    param([byte[]] $Bytes, [long] $Offset, [string] $Context)
    if ($Offset -lt 0 -or $Offset + 4 -gt $Bytes.LongLength) {
        Fail-Bootstrap 'MBV_ZIP_BOUNDS' 'ZIP structure exceeds archive bounds.' $Context
    }
    return [System.BitConverter]::ToUInt32($Bytes, [int] $Offset)
}

function Get-AsciiName {
    param([byte[]] $Bytes, [long] $Offset, [int] $Length, [string] $Context)
    if ($Offset -lt 0 -or $Offset + $Length -gt $Bytes.LongLength) {
        Fail-Bootstrap 'MBV_ZIP_BOUNDS' 'ZIP file name exceeds archive bounds.' $Context
    }
    $slice = New-Object byte[] $Length
    if ($Length -gt 0) {
        [System.Array]::Copy($Bytes, $Offset, $slice, 0, $Length)
    }
    if (@($slice | Where-Object { $_ -gt 127 }).Count -ne 0) {
        Fail-Bootstrap 'MBV_ZIP_NAME_ENCODING' 'Deterministic MALTS ZIP names must be ASCII-compatible.' $Context
    }
    return [System.Text.Encoding]::ASCII.GetString($slice)
}

function Assert-SafeArchivePath {
    param([string] $Value, [string] $ExpectedRoot)
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Contains('\') -or -not $Value.StartsWith($ExpectedRoot + '/', [System.StringComparison]::Ordinal)) {
        Fail-Bootstrap 'MBV_ARCHIVE_ROOT' 'Archive member is outside the expected top-level directory.' $Value
    }
    if ($Value.Length -gt 32760 -or $Value -match '[<>:"|?*\x00-\x1F]') {
        Fail-Bootstrap 'MBV_UNSAFE_PATH' 'Archive member contains an unsupported Windows path character or length.' $Value
    }
    foreach ($part in $Value.Split('/')) {
        if ([string]::IsNullOrWhiteSpace($part) -or $part -eq '.' -or $part -eq '..' -or $part.Length -gt 255 -or $part.EndsWith(' ') -or $part.EndsWith('.')) {
            Fail-Bootstrap 'MBV_UNSAFE_PATH' 'Archive member contains an unsafe path segment.' $Value
        }
        $stem = $part.Split('.')[0].TrimEnd(' ', '.').ToUpperInvariant()
        if ($script:ReservedNames -contains $stem) {
            Fail-Bootstrap 'MBV_RESERVED_PATH' 'Archive member contains a Windows reserved name.' $Value
        }
    }
}

function Get-ZipRecords {
    param([string] $Archive, [string] $ExpectedRoot)
    if ((Get-Item -LiteralPath $Archive).Length -gt [int]::MaxValue) {
        Fail-Bootstrap 'MBV_ZIP64' 'Bootstrap verification accepts only non-ZIP64 archives smaller than 2 GiB.' $Archive
    }
    $bytes = [System.IO.File]::ReadAllBytes($Archive)
    if ($bytes.LongLength -lt 22) {
        Fail-Bootstrap 'MBV_ZIP_INVALID' 'Archive is too short to contain an EOCD record.' $Archive
    }

    $minimum = [Math]::Max(0, $bytes.LongLength - 65557)
    $eocd = -1L
    for ($offset = $bytes.LongLength - 22; $offset -ge $minimum; $offset--) {
        if ((Read-U32 $bytes $offset 'EOCD') -eq 0x06054B50) {
            $commentLength = Read-U16 $bytes ($offset + 20) 'EOCD comment'
            if ($offset + 22 + $commentLength -eq $bytes.LongLength) {
                $eocd = $offset
                break
            }
        }
    }
    if ($eocd -lt 0) {
        Fail-Bootstrap 'MBV_ZIP_INVALID' 'A canonical EOCD record was not found.' $Archive
    }
    if ((Read-U16 $bytes ($eocd + 4) 'EOCD disk') -ne 0 -or (Read-U16 $bytes ($eocd + 6) 'EOCD central disk') -ne 0) {
        Fail-Bootstrap 'MBV_ZIP_MULTIDISK' 'Multi-disk ZIP archives are forbidden.' $Archive
    }
    $entryCount = Read-U16 $bytes ($eocd + 10) 'EOCD entry count'
    if ($entryCount -eq 0xFFFF -or (Read-U16 $bytes ($eocd + 8) 'EOCD disk entry count') -ne $entryCount) {
        Fail-Bootstrap 'MBV_ZIP64' 'ZIP64 or inconsistent entry counts are forbidden for MALTS transport.' $Archive
    }
    $centralSize = [long](Read-U32 $bytes ($eocd + 12) 'EOCD central size')
    $centralOffset = [long](Read-U32 $bytes ($eocd + 16) 'EOCD central offset')
    if ($centralOffset + $centralSize -ne $eocd) {
        Fail-Bootstrap 'MBV_ZIP_LAYOUT' 'Central directory does not end at the EOCD record.' $Archive
    }

    $records = New-Object System.Collections.Generic.List[object]
    $ranges = New-Object System.Collections.Generic.List[object]
    $seen = @{}
    $cursor = $centralOffset
    for ($index = 0; $index -lt $entryCount; $index++) {
        if ((Read-U32 $bytes $cursor 'central header') -ne 0x02014B50) {
            Fail-Bootstrap 'MBV_ZIP_LAYOUT' 'Invalid central-directory header signature.' $Archive
        }
        $flags = Read-U16 $bytes ($cursor + 8) 'central flags'
        $versionMadeBy = Read-U16 $bytes ($cursor + 4) 'central creator version'
        $versionNeeded = Read-U16 $bytes ($cursor + 6) 'central required version'
        $method = Read-U16 $bytes ($cursor + 10) 'central method'
        $time = Read-U16 $bytes ($cursor + 12) 'central time'
        $date = Read-U16 $bytes ($cursor + 14) 'central date'
        $crc = Read-U32 $bytes ($cursor + 16) 'central crc'
        $compressed = [long](Read-U32 $bytes ($cursor + 20) 'central compressed size')
        $uncompressed = [long](Read-U32 $bytes ($cursor + 24) 'central uncompressed size')
        $nameLength = Read-U16 $bytes ($cursor + 28) 'central name length'
        $extraLength = Read-U16 $bytes ($cursor + 30) 'central extra length'
        $commentLength = Read-U16 $bytes ($cursor + 32) 'central comment length'
        $diskStart = Read-U16 $bytes ($cursor + 34) 'central disk start'
        $internal = Read-U16 $bytes ($cursor + 36) 'central internal attributes'
        $external = Read-U32 $bytes ($cursor + 38) 'central external attributes'
        $localOffset = [long](Read-U32 $bytes ($cursor + 42) 'central local offset')
        $name = Get-AsciiName $bytes ($cursor + 46) $nameLength 'central name'

        Assert-SafeArchivePath $name $ExpectedRoot
        $folded = $name.ToLowerInvariant()
        if ($seen.ContainsKey($folded)) {
            Fail-Bootstrap 'MBV_CASE_COLLISION' 'Archive members collide under Windows case folding.' $name
        }
        $seen[$folded] = $true
        $mode = [int](($external -shr 16) -band 0xFFFF)
        if ($versionMadeBy -ne 788 -or $versionNeeded -ne 20 -or $flags -ne 0 -or $method -ne 0 -or $time -ne 0 -or $date -ne 33 -or $extraLength -ne 0 -or $commentLength -ne 0 -or $diskStart -ne 0 -or $internal -ne 0 -or $external -ne [uint32]2175008768 -or $mode -ne 33188) {
            Fail-Bootstrap 'MBV_ZIP_PROFILE' 'Archive member does not match MALTS-ZIP-STORED-UTC-1980-v1.' $name
        }
        if ($compressed -ne $uncompressed) {
            Fail-Bootstrap 'MBV_ZIP_PROFILE' 'Stored archive member has unequal compressed and uncompressed lengths.' $name
        }
        if ($uncompressed -gt [int]::MaxValue) {
            Fail-Bootstrap 'MBV_ZIP64' 'Archive member exceeds the bootstrap verifier size limit.' $name
        }

        if ((Read-U32 $bytes $localOffset 'local header') -ne 0x04034B50) {
            Fail-Bootstrap 'MBV_ZIP_LAYOUT' 'Invalid local-file header signature.' $name
        }
        $localFlags = Read-U16 $bytes ($localOffset + 6) 'local flags'
        $localVersion = Read-U16 $bytes ($localOffset + 4) 'local required version'
        $localMethod = Read-U16 $bytes ($localOffset + 8) 'local method'
        $localTime = Read-U16 $bytes ($localOffset + 10) 'local time'
        $localDate = Read-U16 $bytes ($localOffset + 12) 'local date'
        $localCrc = Read-U32 $bytes ($localOffset + 14) 'local crc'
        $localCompressed = [long](Read-U32 $bytes ($localOffset + 18) 'local compressed size')
        $localUncompressed = [long](Read-U32 $bytes ($localOffset + 22) 'local uncompressed size')
        $localNameLength = Read-U16 $bytes ($localOffset + 26) 'local name length'
        $localExtraLength = Read-U16 $bytes ($localOffset + 28) 'local extra length'
        $localName = Get-AsciiName $bytes ($localOffset + 30) $localNameLength 'local name'
        if ($localVersion -ne $versionNeeded -or $localFlags -ne $flags -or $localMethod -ne $method -or $localTime -ne $time -or $localDate -ne $date -or $localCrc -ne $crc -or $localCompressed -ne $compressed -or $localUncompressed -ne $uncompressed -or $localExtraLength -ne 0 -or $localName -cne $name) {
            Fail-Bootstrap 'MBV_ZIP_LAYOUT' 'Central and local ZIP headers disagree.' $name
        }

        $dataOffset = $localOffset + 30 + $localNameLength + $localExtraLength
        $dataEnd = $dataOffset + $uncompressed
        if ($dataEnd -gt $centralOffset) {
            Fail-Bootstrap 'MBV_ZIP_BOUNDS' 'Archive member data overlaps the central directory.' $name
        }
        $payload = New-Object byte[] ([int] $uncompressed)
        if ($uncompressed -gt 0) {
            [System.Array]::Copy($bytes, $dataOffset, $payload, 0, $uncompressed)
        }
        $ranges.Add([pscustomobject]@{ Start = $localOffset; End = $dataEnd; Path = $name })
        $records.Add([pscustomobject]@{ Path = $name; Bytes = $uncompressed; Sha256 = (Get-Sha256Bytes $payload); Data = $payload })
        $cursor += 46 + $nameLength + $extraLength + $commentLength
    }
    if ($cursor -ne $centralOffset + $centralSize) {
        Fail-Bootstrap 'MBV_ZIP_LAYOUT' 'Central-directory byte length is inconsistent.' $Archive
    }
    $lastEnd = 0L
    foreach ($range in @($ranges | Sort-Object Start)) {
        if ($range.Start -ne $lastEnd) {
            Fail-Bootstrap 'MBV_ZIP_LAYOUT' 'Archive local records contain a gap, overlap, or preamble.' $range.Path
        }
        $lastEnd = $range.End
    }
    if ($lastEnd -ne $centralOffset) {
        Fail-Bootstrap 'MBV_ZIP_LAYOUT' 'Archive local records do not end at the central directory.' $Archive
    }
    return $records.ToArray()
}

function Escape-CanonicalJsonString {
    param([string] $Value)
    return $Value.Replace('\', '\\').Replace('"', '\"')
}

function Get-InventoryTreeSha256 {
    param([object[]] $Records)
    $parts = foreach ($record in $Records) {
        '{"bytes":' + [string]$record.Bytes + ',"path":"' + (Escape-CanonicalJsonString $record.Path) + '","sha256":"' + $record.Sha256 + '"}'
    }
    return Get-Sha256Bytes ($script:Utf8NoBom.GetBytes('[' + ($parts -join ',') + ']'))
}

function Get-RecordMap {
    param([object[]] $Records)
    $map = @{}
    foreach ($record in $Records) {
        $map[$record.Path.ToLowerInvariant()] = $record
    }
    return $map
}

function Assert-NoReparseAncestors {
    param([string] $Path)
    $current = New-Object System.IO.DirectoryInfo -ArgumentList ([System.IO.Path]::GetFullPath($Path))
    while ($null -ne $current) {
        if ($current.Exists -and (($current.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            Fail-Bootstrap 'MBV_REPARSE' 'Extraction path contains a reparse point.' $current.FullName
        }
        $current = $current.Parent
    }
}

function Write-VerifiedRecords {
    param([object[]] $Records, [string] $Destination)
    if ([System.IO.Directory]::Exists($Destination) -or [System.IO.File]::Exists($Destination)) {
        Fail-Bootstrap 'MBV_EXTRACT_EXISTS' 'Extraction destination must not already exist.' $Destination
    }
    Assert-NoReparseAncestors ([System.IO.Path]::GetDirectoryName($Destination))
    [System.IO.Directory]::CreateDirectory($Destination) | Out-Null
    foreach ($record in $Records) {
        $relative = $record.Path.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        $target = [System.IO.Path]::GetFullPath((Join-Path $Destination $relative))
        $prefix = $Destination.TrimEnd('\') + '\'
        if (-not $target.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            Fail-Bootstrap 'MBV_PATH_ESCAPE' 'Verified member escaped extraction root.' $record.Path
        }
        $parent = [System.IO.Path]::GetDirectoryName($target)
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
        Assert-NoReparseAncestors $parent
        [System.IO.File]::WriteAllBytes($target, $record.Data)
    }
}

function Invoke-UserPackageVerifier {
    param([string] $ReleaseRoot)
    $engine = Join-Path $ReleaseRoot 'lifecycle_artifact\payload\tools\malts_lifecycle.py'
    if (-not [System.IO.File]::Exists($engine)) {
        Fail-Bootstrap 'MBV_USER_VERIFIER' 'Verified archive does not contain the user lifecycle verifier.' $engine
    }
    $output = & python -B $engine verify-release --release-root $ReleaseRoot 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail-Bootstrap 'MBV_USER_VERIFIER' "The extracted user verifier failed: $($output -join ' ')" $ReleaseRoot
    }
}

$archive = Get-FullPath $ArchivePath
if (-not [System.IO.File]::Exists($archive)) {
    Fail-Bootstrap 'MBV_INPUT_MISSING' 'Archive file was not found.' $archive
}
$assetRoot = [System.IO.Path]::GetDirectoryName($archive)
$archiveName = [System.IO.Path]::GetFileName($archive)
$archiveStem = [System.IO.Path]::GetFileNameWithoutExtension($archive)
$transportPath = if ([string]::IsNullOrWhiteSpace($TransportManifestPath)) { Join-Path $assetRoot ($archiveStem + '.transport.json') } else { Get-FullPath $TransportManifestPath }
$checksum = if ([string]::IsNullOrWhiteSpace($ChecksumPath)) { $archive + '.sha256' } else { Get-FullPath $ChecksumPath }
foreach ($path in @($transportPath, $checksum)) {
    if (-not [System.IO.File]::Exists($path)) {
        Fail-Bootstrap 'MBV_INPUT_MISSING' 'Required adjacent transport input was not found.' $path
    }
}

try {
    $transport = [System.IO.File]::ReadAllText($transportPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
}
catch {
    Fail-Bootstrap 'MBV_MANIFEST_JSON' "Transport manifest is invalid JSON: $($_.Exception.Message)" $transportPath
}
Assert-ExactProperties $transport @('schema_version','release_id','version','release_manifest_sha256','release_package_sha256','archive','checksum','expected_top_level_directory','exact_inventory','hosted_assets','created_at') 'transport'
Assert-ExactProperties $transport.archive @('file','format','deterministic_profile','bytes','sha256') 'transport.archive'
Assert-ExactProperties $transport.checksum @('file','algorithm','sha256') 'transport.checksum'
Assert-ExactProperties $transport.exact_inventory @('file_count','tree_sha256','files') 'transport.exact_inventory'
if ([int]$transport.schema_version -ne 1 -or $transport.release_id -cnotmatch '^MALTS-[0-9]+\.[0-9]+\.[0-9]+$' -or $transport.version -cne $script:BootstrapVersion -or $transport.release_id -cne ('MALTS-' + $transport.version) -or $transport.expected_top_level_directory -cne $transport.release_id) {
    Fail-Bootstrap 'MBV_MANIFEST_IDENTITY' "Transport identity must match bootstrap tag $($script:BootstrapTag)." $transportPath
}
Assert-Sha256 ([string]$transport.release_manifest_sha256) 'release_manifest_sha256'
Assert-Sha256 ([string]$transport.release_package_sha256) 'release_package_sha256'
Assert-Sha256 ([string]$transport.archive.sha256) 'archive.sha256'
Assert-Sha256 ([string]$transport.checksum.sha256) 'checksum.sha256'
Assert-Sha256 ([string]$transport.exact_inventory.tree_sha256) 'exact_inventory.tree_sha256'
if ($transport.archive.file -cne $archiveName -or $transport.archive.format -cne 'zip' -or $transport.archive.deterministic_profile -cne 'MALTS-ZIP-STORED-UTC-1980-v1' -or $transport.checksum.file -cne [System.IO.Path]::GetFileName($checksum) -or $transport.checksum.algorithm -cne 'SHA256') {
    Fail-Bootstrap 'MBV_SIDECAR_BINDING' 'Archive or checksum names/profile do not match the transport manifest.' $transportPath
}

$hosted = @($transport.hosted_assets)
if ($hosted.Count -ne 4) {
    Fail-Bootstrap 'MBV_HOSTED_ASSETS' 'Transport must declare exactly four hosted assets.' $transportPath
}
$hostedMap = @{}
foreach ($entry in $hosted) {
    Assert-ExactProperties $entry @('kind','file') 'hosted_assets[]'
    if ($hostedMap.ContainsKey([string]$entry.kind)) {
        Fail-Bootstrap 'MBV_HOSTED_ASSETS' 'Hosted asset kinds must be unique.' ([string]$entry.kind)
    }
    $hostedMap[[string]$entry.kind] = [string]$entry.file
}
$actualHostedKinds = @(($hostedMap.Keys | Sort-Object)) -join ','
$expectedHostedKinds = @('archive','checksum','release-notes','transport-manifest') -join ','
if ($actualHostedKinds -cne $expectedHostedKinds -or $hostedMap.archive -cne $archiveName -or $hostedMap.checksum -cne [System.IO.Path]::GetFileName($checksum) -or $hostedMap.'transport-manifest' -cne [System.IO.Path]::GetFileName($transportPath)) {
    Fail-Bootstrap 'MBV_HOSTED_ASSETS' 'Hosted assets do not match the exact four-asset contract.' $transportPath
}
$notes = if ([string]::IsNullOrWhiteSpace($ReleaseNotesPath)) { Join-Path $assetRoot $hostedMap.'release-notes' } else { Get-FullPath $ReleaseNotesPath }
if (-not [System.IO.File]::Exists($notes) -or [System.IO.Path]::GetFileName($notes) -cne $hostedMap.'release-notes') {
    Fail-Bootstrap 'MBV_INPUT_MISSING' 'Public release notes asset was not found under its hosted name.' $notes
}

$archiveHash = Get-Sha256File $archive
$archiveLength = (Get-Item -LiteralPath $archive).Length
if ($archiveLength -ne [long]$transport.archive.bytes -or $archiveHash -cne [string]$transport.archive.sha256) {
    Fail-Bootstrap 'MBV_ARCHIVE_HASH' 'Archive bytes or SHA-256 do not match the transport manifest.' $archive
}
$checksumHash = Get-Sha256File $checksum
if ($checksumHash -cne [string]$transport.checksum.sha256) {
    Fail-Bootstrap 'MBV_CHECKSUM_HASH' 'Checksum sidecar hash does not match the transport manifest.' $checksum
}
$expectedChecksum = $script:Utf8NoBom.GetBytes($archiveHash + '  ' + $archiveName + "`n")
$actualChecksum = [System.IO.File]::ReadAllBytes($checksum)
if ([System.Convert]::ToBase64String($expectedChecksum) -cne [System.Convert]::ToBase64String($actualChecksum)) {
    Fail-Bootstrap 'MBV_CHECKSUM_CONTENT' 'Checksum sidecar content is not canonical or does not bind the archive.' $checksum
}

$records = @(Get-ZipRecords $archive ([string]$transport.expected_top_level_directory))
$manifestRecords = @($transport.exact_inventory.files)
if ($records.Count -ne [int]$transport.exact_inventory.file_count -or $records.Count -ne $manifestRecords.Count) {
    Fail-Bootstrap 'MBV_INVENTORY_COUNT' 'Archive and manifest inventory counts differ.' $archive
}
for ($index = 0; $index -lt $records.Count; $index++) {
    Assert-ExactProperties $manifestRecords[$index] @('path','bytes','sha256') "exact_inventory.files[$index]"
    Assert-Sha256 ([string]$manifestRecords[$index].sha256) "exact_inventory.files[$index].sha256"
    if ($records[$index].Path -cne [string]$manifestRecords[$index].path -or $records[$index].Bytes -ne [long]$manifestRecords[$index].bytes -or $records[$index].Sha256 -cne [string]$manifestRecords[$index].sha256) {
        Fail-Bootstrap 'MBV_INVENTORY_MISMATCH' 'Archive member does not match the exact ordered inventory.' $records[$index].Path
    }
}
$treeHash = Get-InventoryTreeSha256 $records
if ($treeHash -cne [string]$transport.exact_inventory.tree_sha256) {
    Fail-Bootstrap 'MBV_TREE_HASH' 'Exact inventory tree hash is invalid.' $transportPath
}
$recordMap = Get-RecordMap $records
$releaseRootName = [string]$transport.expected_top_level_directory
$notesKey = ($releaseRootName + '/RELEASE_NOTES.md').ToLowerInvariant()
$manifestKey = ($releaseRootName + '/release_manifest.json').ToLowerInvariant()
$inventoryKey = ($releaseRootName + '/release_inventory.json').ToLowerInvariant()
foreach ($key in @($notesKey, $manifestKey, $inventoryKey)) {
    if (-not $recordMap.ContainsKey($key)) {
        Fail-Bootstrap 'MBV_PACKAGE_LAYOUT' 'Required outer release file is absent from the exact inventory.' $key
    }
}
if ((Get-Sha256File $notes) -cne $recordMap[$notesKey].Sha256) {
    Fail-Bootstrap 'MBV_RELEASE_NOTES' 'External public release notes do not match the archive-bound notes.' $notes
}
if ($recordMap[$manifestKey].Sha256 -cne [string]$transport.release_manifest_sha256) {
    Fail-Bootstrap 'MBV_RELEASE_MANIFEST' 'Transport does not bind the exact outer ReleaseManifest.' $transportPath
}
$identity = '{"algorithm":"MALTS-RELEASE-PACKAGE-v1","release_inventory_sha256":"' + $recordMap[$inventoryKey].Sha256 + '","release_manifest_sha256":"' + $recordMap[$manifestKey].Sha256 + '"}'
if ((Get-Sha256Bytes $script:Utf8NoBom.GetBytes($identity)) -cne [string]$transport.release_package_sha256) {
    Fail-Bootstrap 'MBV_RELEASE_PACKAGE' 'Logical release-package identity does not match the transport manifest.' $transportPath
}

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MALTS-bootstrap-' + [System.Guid]::NewGuid().ToString('N'))
try {
    Write-VerifiedRecords $records $temporaryRoot
    $temporaryRelease = Join-Path $temporaryRoot $releaseRootName
    Invoke-UserPackageVerifier $temporaryRelease
}
finally {
    if ([System.IO.Directory]::Exists($temporaryRoot)) {
        [System.IO.Directory]::Delete($temporaryRoot, $true)
    }
}

$mode = 'VERIFY_ONLY'
$writesPerformed = $false
$output = $null
if (-not [string]::IsNullOrWhiteSpace($ExtractOutput)) {
    $output = Get-FullPath $ExtractOutput
    if ([System.IO.Path]::GetFileName($output) -cne $releaseRootName) {
        Fail-Bootstrap 'MBV_EXTRACT_NAME' 'Extraction output directory name must equal release_id.' $output
    }
    if ($Apply) {
        if ([System.IO.Directory]::Exists($output) -or [System.IO.File]::Exists($output)) {
            Fail-Bootstrap 'MBV_EXTRACT_EXISTS' 'Extraction output must not already exist.' $output
        }
        $parent = [System.IO.Path]::GetDirectoryName($output)
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
        Assert-NoReparseAncestors $parent
        $stage = Join-Path $parent ('.mb-' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8))
        try {
            Write-VerifiedRecords $records $stage
            $stagedRelease = Join-Path $stage $releaseRootName
            Invoke-UserPackageVerifier $stagedRelease
            [System.IO.Directory]::Move($stagedRelease, $output)
            $mode = 'EXTRACT_APPLY'
            $writesPerformed = $true
        }
        finally {
            if ([System.IO.Directory]::Exists($stage)) {
                [System.IO.Directory]::Delete($stage, $true)
            }
        }
    }
    else {
        $mode = 'EXTRACT_PREVIEW'
    }
}
elseif ($Apply) {
    Fail-Bootstrap 'MBV_APPLY_SCOPE' '-Apply requires -ExtractOutput.' ''
}

[ordered]@{
    status = 'PASS'
    bootstrap_tag = $script:BootstrapTag
    bootstrap_version = $script:BootstrapVersion
    release_id = $transport.release_id
    archive_sha256 = $archiveHash
    release_manifest_sha256 = $transport.release_manifest_sha256
    release_package_sha256 = $transport.release_package_sha256
    inventory_file_count = $records.Count
    exact_four_hosted_assets = $true
    isolated_user_verification_cleaned = $true
    mode = $mode
    writes_performed = $writesPerformed
    output = $output
} | ConvertTo-Json -Depth 6
