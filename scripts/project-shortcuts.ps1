# Puts "<Title> (<Agent>)" links on the Windows desktop, one per agent the launcher profile names
# (.conclave/launchers.json): a double-click opens a terminal in the project with the agent running. Beside them goes
# one "<Title> (<label>)" link per entry of the profile's `links`: a `run` entry runs its command in the project, a
# `url` entry opens its address in the default browser. Each icon is the project's own icon with the agent's or the
# entry's mark in a rounded square in its corner, rendered on this machine.
#
#   pwsh scripts/project-shortcuts.ps1                    a project on a Windows drive, or one opened from its
#                                                         \\wsl.localhost\<distro>\ path (the distro is read from it)
#   pwsh scripts/project-shortcuts.ps1 -Distro Ubuntu -Project /home/me/site
#   pwsh scripts/project-shortcuts.ps1 -Remove            remove every link and icon this script made for the project
#
# A project in WSL opens in Windows Terminal as `wsl.exe -d <distro> --cd <linux path> --exec bash -lic <agent>`: the
# shell is interactive because an owner's wrapper for the agent (one that loads a token, say) lives in ~/.bashrc, after
# its "not interactive: return" guard. A project on a Windows drive opens as `wt.exe -d <project> pwsh.exe -NoLogo
# -NoExit -Command <agent>`. Without Windows Terminal the link starts PowerShell itself, which for a WSL project runs
# wsl.exe and, if WSL fails, says so and waits for Enter. An agent that does not start says so and waits for Enter too.
#
# A `run` entry opens in PowerShell. The command is never spliced into the code that watches it, so its own syntax (an
# `exit`, a trailing comment or `;`) cannot break that code. For a project in WSL the link runs `wsl.exe -d <distro>
# --cd <linux path> --exec bash -lc '(eval "$1") || { echo '<label> did not start: ...'; read -r _; }' bash
# <command>`: the login shell gets the command as its first argument and runs it in a subshell. For a project on a
# Windows drive it runs the command in a child PowerShell (-EncodedCommand) in the project folder. Either way a
# failure stays on screen until Enter. A `url` entry's link starts `rundll32.exe url.dll,
# FileProtocolHandler <url>`, which opens the browser with no console window.
#
# Each project has one identity: its distro and Linux path for a project in WSL (however the path was written), or its
# full Windows path. The links carry it in their description, which is how this script finds its own links, and the
# icons carry a key derived from it, so two projects never touch each other's files. Everything is written under a
# temporary name first and moved into place only when all of it succeeded; a failure leaves every earlier link and
# icon as it was. A link of this project's that the profile no longer names is removed after a successful write.
# The campaign links of the unattended kit carry their own mark and are never touched here.
param(
  [string]$Distro = '',
  [string]$Project = '',
  [string]$ShortcutDir = [Environment]::GetFolderPath('Desktop'),
  [string]$IconDir = '',
  [switch]$Remove,
  [switch]$Inspect,
  # For the tests: a stand-in for wsl.exe, and the Python that reads the profile and renders the icons.
  [string]$Wsl = '',
  [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$root = Split-Path $here   # the project this script is installed in holds the profile
if (-not $Project) { $Project = $root }

function Refuse([string]$why) { "project-shortcuts: $why; nothing was written"; exit 1 }

if ($Remove -and $Inspect) { Refuse 'pass either -Remove or -Inspect, not both' }

# Links are written and read through IShellLinkW (scripts/lib/ShellLink.cs), which also supplies ShellPath.Long so
# existing Windows paths normalize before identity derivation across create, -Remove, and -Inspect.
$shellLink = Join-Path $here 'lib\ShellLink.cs'
if (-not (Test-Path -LiteralPath $shellLink -PathType Leaf)) {
  Refuse "missing $shellLink (python forge.py kit <project> launchers installs it)"
}
Add-Type -LiteralPath $shellLink

# --- the project's identity ---------------------------------------------------------------------------------------
function Get-IdentityKey([string]$id) {
  $h = [System.Security.Cryptography.SHA256]::Create()
  try {
    return -join ($h.ComputeHash([Text.Encoding]::UTF8.GetBytes($id))[0..3] | ForEach-Object { $_.ToString('x2') })
  } finally {
    $h.Dispose()
  }
}

function Get-CanonicalPath([string]$p) {
  if (-not $p) { return '' }
  try { return [Conclave.ShellPath]::Long($p).TrimEnd('\').ToLowerInvariant() }
  catch { return $p.TrimEnd('\').ToLowerInvariant() }
}

$linux = $null
$projectExists = $false
$legacyKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$legacyIconDirs = [Collections.Generic.List[string]]::new()
$iconDirDefaulted = -not [bool]$IconDir
if ($Project -match '^\\\\wsl(?:\.localhost|\$)\\([^\\]+)\\?(.*)$') {
  if (-not $Distro) { $Distro = $Matches[1] }
  elseif ($Matches[1] -ne $Distro) { Refuse "the project is in distro '$($Matches[1])', not '$Distro'" }
  $linux = '/' + ($Matches[2] -replace '\\', '/')
} elseif ($Project.StartsWith('/')) {
  if (-not $Distro) { Refuse "a Linux path needs -Distro to say which WSL distro holds it: '$Project'" }
  $linux = $Project
}
if ($null -ne $linux) {
  $linux = ($linux -replace '/+', '/').TrimEnd('/')
  if (-not $linux) { $linux = '/' }
  # Linux paths keep their case (/srv/Site and /srv/site are two projects); distro names ignore it.
  $identity = "wsl:$($Distro.ToLowerInvariant()):$linux"
  $name = Split-Path $linux -Leaf
} else {
  $found = Resolve-Path -LiteralPath $Project -ErrorAction Ignore
  if ($found) {
    $projectExists = $true
    # ProviderPath strips PowerShell's provider prefix; ShellPath.Long expands 8.3 short names so short, mixed, and
    # long spellings of one Windows folder share one identity.
    $rawPath = $found.ProviderPath.TrimEnd('\')
    $Project = [Conclave.ShellPath]::Long($rawPath).TrimEnd('\')
    $shortPath = [Conclave.ShellPath]::Short($Project).TrimEnd('\')
    foreach ($alt in @($rawPath, $shortPath)) {
      if ($alt -and -not [String]::Equals($alt, $Project, [StringComparison]::OrdinalIgnoreCase)) {
        [void]$legacyKeys.Add((Get-IdentityKey $alt.ToLowerInvariant()))
        if ($iconDirDefaulted) {
          $altName = Split-Path $alt -Leaf
          if ($altName) { $legacyIconDirs.Add((Join-Path $env:LOCALAPPDATA $altName)) }
        }
      }
    }
  } elseif ($Remove -or $Inspect) {
    $Project = [IO.Path]::GetFullPath($Project).TrimEnd('\')   # removal/inspection work when the folder is gone
  } else {
    Refuse "the project folder does not exist: '$Project'"
  }
  $identity = $Project.ToLowerInvariant()   # Windows paths ignore case
  $name = Split-Path $Project -Leaf
}
if (-not $IconDir) { $IconDir = Join-Path $env:LOCALAPPDATA $name }
else {
  [System.Management.Automation.ProviderInfo]$iconProv = $null
  [System.Management.Automation.PSDriveInfo]$iconDrive = $null
  $resolvedIconDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($IconDir, [ref]$iconProv, [ref]$iconDrive)
  if (-not $iconProv -or $iconProv.Name -ne 'FileSystem') {
    $provName = if ($iconProv) { $iconProv.Name } else { 'unknown' }
    Refuse "-IconDir must be a filesystem path (got provider '$provName': '$IconDir')"
  }
  $IconDir = $resolvedIconDir
}
$mark = "conclave-launcher: $identity"
$key = Get-IdentityKey $identity

# Exact code-unit comparison: PowerShell's -ceq/-cne fold canonical Unicode equivalence (composed vs decomposed).
# For an existing Windows directory, also recognize any pre-change short or mixed 8.3 spelling that expands to $Project.
function Test-OwnedMark([string]$desc) {
  if ($null -eq $desc) { return $false }
  if ([String]::Equals($desc, $mark, [StringComparison]::Ordinal)) { return $true }
  if ($null -eq $linux -and $projectExists -and $desc.StartsWith('conclave-launcher: ', [StringComparison]::Ordinal)) {
    $stored = $desc.Substring('conclave-launcher: '.Length)
    if ($stored -and -not $stored.StartsWith('wsl:', [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $stored -PathType Container)) {
      $expanded = [Conclave.ShellPath]::Long($stored).TrimEnd('\')
      if ([String]::Equals($expanded, $Project, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
  }
  return $false
}

# Legacy 8.3 / mixed-spelling icons: deduplicate directories and files by canonical long path so an 8.3 alias of
# $IconDir never enumerates, deletes, or moves the same file twice. Fail closed if an existing icon folder cannot
# be enumerated so -Remove never deletes an ownership link before its icons can be inventoried.
$iconScanError = ''
function Get-LegacyIcons([object[]]$ownedLinks) {
  $script:iconScanError = ''
  $keys = [Collections.Generic.HashSet[string]]::new($legacyKeys, [StringComparer]::Ordinal)
  $dirs = [Collections.Generic.List[string]]::new()
  $dirs.Add($IconDir)
  foreach ($d in $legacyIconDirs) { $dirs.Add($d) }
  foreach ($link in $ownedLinks) {
    $desc = $link.Description
    $iconPath = $link.IconPath
    if ($desc -and -not [String]::Equals($desc, $mark, [StringComparison]::Ordinal) -and $desc.StartsWith('conclave-launcher: ', [StringComparison]::Ordinal)) {
      $storedId = $desc.Substring('conclave-launcher: '.Length)
      $k = Get-IdentityKey $storedId
      if ($k -ne $key) {
        [void]$keys.Add($k)
        if ($iconPath) {
          $parent = Split-Path $iconPath -Parent
          if ($parent) { $dirs.Add($parent) }
        }
      }
    }
  }
  if ($keys.Count -eq 0) { return @() }
  $seenDirs = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
  $seenFiles = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
  $found = [Collections.Generic.List[object]]::new()
  foreach ($dir in $dirs) {
    if (-not $dir) { continue }
    $canonDir = Get-CanonicalPath $dir
    if (-not $seenDirs.Add($canonDir)) { continue }
    foreach ($k in $keys) {
      if ($k -eq $key) { continue }
      try {
        $matches = @([IO.Directory]::GetFiles($dir, "launcher-*-$k.ico"))
      } catch [IO.DirectoryNotFoundException] {
        break
      } catch {
        $script:iconScanError = "the icon folder cannot be read: '$dir' ($($_.Exception.Message))"
        return @()
      }
      foreach ($f in $matches) {
        if ($seenFiles.Add((Get-CanonicalPath $f))) { $found.Add([IO.FileInfo]::new($f)) }
      }
    }
  }
  return @($found)
}

# --- inspection: reads owned links through ShellLink.cs without launching any of them ----------------------------
if ($Inspect) {
  if (-not (Test-Path -LiteralPath $ShortcutDir -PathType Container)) {
    Refuse "the shortcut folder cannot be read: '$ShortcutDir'"
  }
  try {
    $lnkFiles = @(Get-ChildItem -LiteralPath $ShortcutDir -Filter '*.lnk' -File -Force -ErrorAction Stop)
  } catch {
    Refuse "the shortcut folder cannot be read: '$ShortcutDir' ($($_.Exception.Message))"
  }
  $lnkFiles | ForEach-Object {
    $f = $_
    try {
      $l = [Conclave.ShellLink]::Read($f.FullName)
      if (Test-OwnedMark $l.Description) {
        [pscustomobject]@{
          Link        = $f.Name
          Target      = $l.Target
          Arguments   = $l.Arguments
          IconPath    = $l.IconPath
          Description = $l.Description
        }
      }
    } catch {
      [pscustomobject]@{ Link = $f.Name; Error = $_.Exception.Message }
    }
  } | Format-List
  exit 0
}

function Get-Mark([string]$path) {
  try { [Conclave.ShellLink]::Read($path).Description } catch { '' }
}

# Every .lnk in the shortcut folder (hidden ones too) whose mark is this project's. Unrelated corrupt files are skipped;
# a sharing or access error (0x80070020 or 0x80070005) may hide an owned link, so it is recorded in $unreadableLinks and
# the caller stops before changing any link or icon.
$unreadableLinks = [Collections.Generic.List[string]]::new()
$scanError = ''
function Get-Owned {
  $script:unreadableLinks.Clear()
  $script:scanError = ''
  if (-not (Test-Path -LiteralPath $ShortcutDir)) { return }
  if (-not (Test-Path -LiteralPath $ShortcutDir -PathType Container)) {
    $script:scanError = "the shortcut folder cannot be read: '$ShortcutDir'"
    return
  }
  try {
    $entries = @(Get-ChildItem -LiteralPath $ShortcutDir -Filter '*.lnk' -File -Force -ErrorAction Stop)
  } catch {
    $script:scanError = "the shortcut folder cannot be read: '$ShortcutDir' ($($_.Exception.Message))"
    return
  }
  foreach ($file in $entries) {
    try {
      $data = [Conclave.ShellLink]::Read($file.FullName)
    } catch {
      $cause = $_.Exception
      while ($cause.InnerException) { $cause = $cause.InnerException }
      # 0x80070020 (ERROR_SHARING_VIOLATION) or 0x80070005 (E_ACCESSDENIED): may be this project's link.
      if ($cause.HResult -in @(-2147024864, -2147024891)) {
        if (-not $script:unreadableLinks.Contains($file.FullName)) { $script:unreadableLinks.Add($file.FullName) }
      }
      continue
    }
    if (Test-OwnedMark $data.Description) {
      [pscustomobject]@{
        FullName    = $file.FullName
        Name        = $file.Name
        Description = $data.Description
        IconPath    = $data.IconPath
      }
    }
  }
}

# --- removal: needs nothing but the identity ----------------------------------------------------------------------
if ($Remove) {
  $links = @(Get-Owned)
  if ($scanError) { Refuse $scanError }
  if ($unreadableLinks.Count -gt 0) {
    Refuse "could not read '$($unreadableLinks -join "', '")' to check ownership (close whatever holds it and retry)"
  }
  $icons = [Collections.Generic.List[object]]::new()
  $seenIcons = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
  try {
    $primaryIcons = @([IO.Directory]::GetFiles($IconDir, "launcher-*-$key.ico"))
  } catch [IO.DirectoryNotFoundException] {
    $primaryIcons = @()
  } catch {
    Refuse "the icon folder cannot be read: '$IconDir' ($($_.Exception.Message))"
  }
  foreach ($file in $primaryIcons) {
    if ($seenIcons.Add((Get-CanonicalPath $file))) { $icons.Add([IO.FileInfo]::new($file)) }
  }
  # Read legacy marks/icon paths from owned links before deleting the links.
  $legacyFound = @(Get-LegacyIcons $links)
  if ($iconScanError) { Refuse $iconScanError }
  foreach ($file in $legacyFound) {
    if ($seenIcons.Add((Get-CanonicalPath $file.FullName))) { $icons.Add($file) }
  }
  foreach ($link in $links) { Remove-Item -LiteralPath $link.FullName -Force; "removed: $($link.FullName)" }
  foreach ($file in $icons) { Remove-Item -LiteralPath $file.FullName -Force; "removed: $($file.FullName)" }
  "project-shortcuts: $($links.Count) link(s) and $($icons.Count) icon(s) of $identity removed"
  exit 0
}

# --- what to write ------------------------------------------------------------------------------------------------
if (-not $Python) {
  $Python = (Get-Command python -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
}
if (-not $Python) { Refuse 'python is not on PATH' }
# The profile, read by the kit's own loader, so a profile it refuses is refused here with its own message.
$read = & $Python -B (Join-Path $here 'lib\launchers.py') show --root $root 2>&1
if ($LASTEXITCODE -ne 0) { Refuse "the launcher profile cannot be read: $(($read | Out-String).Trim())" }
$launch = ($read | Select-Object -Last 1) | ConvertFrom-Json
$brand = (Resolve-Path -LiteralPath (Join-Path $root $launch.icon)).ProviderPath

$needsWsl = ($null -ne $linux) -or (@($launch.links | Where-Object { $_.PSObject.Properties['wsl'] -and $_.wsl -eq $true }).Count -gt 0)
if ($needsWsl) {
  if (-not $Wsl) {
    $Wsl = (Get-Command wsl.exe -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
  }
  if (-not $Wsl) { Refuse 'wsl.exe is not on PATH: install WSL' }
  $env:WSL_UTF8 = '1'  # wsl.exe lists its distros in UTF-16 otherwise
  $listed = @(& $Wsl -l -q 2>$null | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ })
  if ($null -ne $linux -or $Distro) {
    if ($LASTEXITCODE -ne 0 -or $listed -notcontains $Distro) {
      Refuse "WSL has no distro '$Distro' (it lists: $($listed -join ', '))"
    }
  } elseif ($LASTEXITCODE -ne 0 -or $listed.Count -eq 0) {
    Refuse 'WSL has no installed distro: install a WSL distribution'
  }
  if ($null -ne $linux) {
    & $Wsl -d $Distro --exec test -d $linux 2>$null
    if ($LASTEXITCODE -ne 0) { Refuse "the project path '$linux' does not exist in '$Distro'" }
  }
}

$labels = [ordered]@{ claude = 'Claude'; codex = 'Codex'; agy = 'Antigravity' }
# The flag each agent's CLI takes to skip its permission prompts, as scripts/unattended-run.py passes it (a test in
# the SDK holds the two equal).
$skipFlags = @{ claude = '--dangerously-skip-permissions'; codex = '--dangerously-bypass-approvals-and-sandbox';
                agy = '--dangerously-skip-permissions' }

# One argument as the Windows command line passes it (backslashes doubled before a quote, the quote escaped).
function Quote([string]$arg) {
  if ($arg -and $arg -notmatch '[\s"]') { return $arg }
  '"' + ($arg -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}
# A PowerShell string literal of any text.
function PSQuote([string]$text) { "'" + $text.Replace("'", "''") + "'" }
# A Bash single-quoted word of any text (a quote inside it closes the word, writes an escaped quote and reopens it).
function BashQuote([string]$text) { "'" + $text.Replace("'", "'\''") + "'" }

$wt = (Get-Command wt.exe -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
$pwshExe = (Get-Process -Id $PID).Path  # the PowerShell 7 that runs this script runs the links too
$ownedBefore = @(Get-Owned)
if ($scanError) { Refuse $scanError }
if ($unreadableLinks.Count -gt 0) {
  Refuse "could not read '$($unreadableLinks -join "', '")' to check ownership (close whatever holds it and retry)"
}
$ownedNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($owned in $ownedBefore) { [void]$ownedNames.Add($owned.Name) }
$plan = @()
foreach ($agent in $launch.agents) {
  $label = "$($launch.title) ($($labels[$agent]))"
  $link = Join-Path $ShortcutDir "$label.lnk"
  # A name another project or anything else holds is never written over.
  if (Test-Path -LiteralPath $link) {
    if (-not (Test-Path -LiteralPath $link -PathType Leaf) -or -not $ownedNames.Contains((Split-Path $link -Leaf))) {
      Refuse "'$link' is already there and is not this project's link"
    }
  }
  $command = if ($launch.skip_permissions) { "$agent $($skipFlags[$agent])" } else { $agent }
  if ($null -ne $linux) {
    # No semicolon: Windows Terminal would read one as the start of its own next command.
    $bash = "$command || (echo '$($labels[$agent]) did not start: the reason is above. Press Enter to close.' && read -r _)"
    $wslWords = @('-d', $Distro, '--cd', $linux, '--exec', 'bash', '-lic', $bash)
    if ($wt) {
      $target = $wt; $arguments = (@($Wsl) + $wslWords | ForEach-Object { Quote $_ }) -join ' '
    } else {
      $code = "& $(PSQuote $Wsl) $(($wslWords | ForEach-Object { PSQuote $_ }) -join ' '); if (`$LASTEXITCODE -ne 0) { " +
        "Write-Host ('WSL could not open the project (exit ' + `$LASTEXITCODE + '): the reason is above. " +
        "Press Enter to close.'); [void][Console]::ReadLine() }"
      $target = $pwshExe; $arguments = "-NoLogo -NoProfile -Command $(Quote $code)"
    }
    $workdir = $env:USERPROFILE
  } else {
    $pwshWords = @('-NoLogo', '-NoExit', '-Command', $command)
    if ($wt) { $target = $wt; $words = @('-d', $Project, $pwshExe) + $pwshWords } else { $target = $pwshExe; $words = $pwshWords }
    $arguments = ($words | ForEach-Object { Quote $_ }) -join ' '
    $workdir = $Project
  }
  $plan += [pscustomobject]@{ Mark = $agent; Label = $label; Link = $link; Target = $target; Arguments = $arguments
                              Workdir = $workdir; Icon = (Join-Path $IconDir "launcher-$agent-$key.ico") }
}
# The profile's declared links (its loader has checked each: a label no agent or other entry uses, a known mark, and a
# one-line command or an http(s) address with no whitespace).
foreach ($entry in @($launch.links)) {
  $label = "$($launch.title) ($($entry.label))"
  $link = Join-Path $ShortcutDir "$label.lnk"
  if (Test-Path -LiteralPath $link) {
    if (-not (Test-Path -LiteralPath $link -PathType Leaf) -or -not $ownedNames.Contains((Split-Path $link -Leaf))) {
      Refuse "'$link' is already there and is not this project's link"
    }
  }
  # The icon's name: the label in lower case, each run of other characters one hyphen (launchers.py's slug).
  $slug = ($entry.label.ToLowerInvariant() -creplace '[^a-z0-9]+', '-').Trim('-')
  if ($entry.PSObject.Properties['url']) {
    $target = Join-Path $env:SystemRoot 'System32\rundll32.exe'
    $arguments = "url.dll,FileProtocolHandler $($entry.url)"
    $workdir = $env:USERPROFILE
  } else {
    $failed = "$($entry.label) did not start: the reason is above. Press Enter to close."
    $useWsl = ($null -ne $linux) -or ($entry.PSObject.Properties['wsl'] -and $entry.wsl -eq $true)
    if ($useWsl) {
      $bash = "(eval `"`$1`") || { echo $(BashQuote $failed); read -r _; }"
      $wslTargetDir = if ($null -ne $linux) { $linux } else { $Project }
      $wslWords = @(if ($Distro) { '-d', $Distro }) + @('--cd', $wslTargetDir, '--exec', 'bash', '-lc', $bash, 'bash', $entry.run)
      $wslFailed = PSQuote "$($entry.label): WSL could not open the project (exit "
      # Standard passing, stated: the command reaches wsl.exe with its quotes whatever the default mode does to them.
      $code = "`$PSNativeCommandArgumentPassing = 'Standard'; " +
        "& $(PSQuote $Wsl) $(($wslWords | ForEach-Object { PSQuote $_ }) -join ' '); if (`$LASTEXITCODE -ne 0) { " +
        "Write-Host ($wslFailed + `$LASTEXITCODE + '): the reason is above. Press Enter to close.'); " +
        "[void][Console]::ReadLine() }"
      $workdir = $env:USERPROFILE
    } else {
      # The child PowerShell parses and runs the command alone: a parse error, a throw or an exit of its own ends the
      # child with a non-zero code, which this waits on.
      $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes(
        "`$ErrorActionPreference = 'Stop'`n$($entry.run)`n"))
      $code = "& $(PSQuote $pwshExe) -NoLogo -NoProfile -EncodedCommand $encoded; if (`$LASTEXITCODE -ne 0) { " +
        "Write-Host $(PSQuote $failed); [void][Console]::ReadLine() }"
      $workdir = $Project
    }
    $target = $pwshExe
    $arguments = "-NoLogo -NoProfile -Command $(Quote $code)"
  }
  $plan += [pscustomobject]@{ Mark = $entry.mark; Label = $label; Link = $link; Target = $target
                              Arguments = $arguments; Workdir = $workdir
                              Icon = (Join-Path $IconDir "launcher-$slug-$key.ico") }
}

# --- write: everything staged, then moved into place together ----------------------------------------------------
New-Item -ItemType Directory -Force -Path $IconDir, $ShortcutDir | Out-Null
$renderer = Join-Path $here 'campaign-icon.py'
$staged = [System.Collections.Generic.List[object]]::new()   # (temporary file, destination)
function Unstage { foreach ($s in $staged) { Remove-Item -LiteralPath $s.Temp -Force -ErrorAction Ignore } }
try {
  foreach ($item in $plan) {
    $iconTemp = "$($item.Icon).$PID.tmp.ico"
    $staged.Add([pscustomobject]@{ Temp = $iconTemp; Dest = $item.Icon; IsLink = $false })
    $out = & $Python -B $renderer overlay $brand $item.Mark $iconTemp 2>&1
    if ($LASTEXITCODE -ne 0) { throw "the icon for $($item.Label) could not be rendered: $(($out | Out-String).Trim())" }
    $linkTemp = Join-Path $ShortcutDir "$($item.Label).$PID.tmp.lnk"
    $staged.Add([pscustomobject]@{ Temp = $linkTemp; Dest = $item.Link; IsLink = $true })
    $data = [Conclave.ShellLinkData]::new()
    $data.Target = $item.Target
    $data.Arguments = $item.Arguments
    $data.WorkingDirectory = $item.Workdir
    $data.Description = $mark
    $data.IconPath = $item.Icon
    $data.IconIndex = 0
    [Conclave.ShellLink]::Write($linkTemp, $data)
  }
} catch {
  Unstage
  "project-shortcuts: $($_.Exception.Message); every earlier link and icon is kept"
  exit 1
}
$moved = [System.Collections.Generic.List[object]]::new()   # (destination, backup or null), to put back on a failure
# A link of this project's that this run does not write (an agent taken out of the profile, an earlier title) goes,
# with its icon, so the desktop holds exactly what the profile names: moved aside in the same step as the new files.
# Compared by file name in the folder, never by full path: the folder may be spelled another way than the one the
# file system reports (a short 8.3 name, a .. segment), which once listed this run's own temporary links as stale:
# after they were renamed into place the stale step could not find them, and the whole run rolled back.
$written = @($plan | ForEach-Object { Split-Path $_.Link -Leaf }) + @($staged | ForEach-Object { Split-Path $_.Temp -Leaf })
$kept = @($plan | ForEach-Object { Split-Path $_.Icon -Leaf })
$staleLinks = @($ownedBefore | Where-Object { $written -notcontains $_.Name } | ForEach-Object { $_.FullName })
$staleIconList = [Collections.Generic.List[string]]::new()
$seenStaleIcons = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($f in @(Get-ChildItem -LiteralPath $IconDir -Filter "launcher-*-$key.ico" -File -ErrorAction Ignore | Where-Object { $kept -notcontains $_.Name })) {
  if ($seenStaleIcons.Add((Get-CanonicalPath $f.FullName))) { $staleIconList.Add($f.FullName) }
}
$staleLegacy = @(Get-LegacyIcons $ownedBefore)
if ($iconScanError) {
  Unstage
  "project-shortcuts: $iconScanError; every earlier link and icon is kept"
  exit 1
}
foreach ($f in $staleLegacy) {
  if ($seenStaleIcons.Add((Get-CanonicalPath $f.FullName))) { $staleIconList.Add($f.FullName) }
}
$staleIcons = @($staleIconList)
$stale = $staleLinks + $staleIcons
try {
  foreach ($s in $staged) {
    $backup = $null
    if (Test-Path -LiteralPath $s.Dest) {
      $backup = "$($s.Dest).$PID.old"
      Move-Item -LiteralPath $s.Dest -Destination $backup
    }
    $entry = [pscustomobject]@{ Dest = $s.Dest; Backup = $backup; Placed = $false }
    $moved.Add($entry)
    # Verify ownership of any link that appeared or changed at a planned destination during staging.
    if ($s.IsLink -and $backup -and -not (Test-OwnedMark (Get-Mark $backup))) {
      throw "'$($s.Dest)' changed during the run and is no longer this project's link"
    }
    Move-Item -LiteralPath $s.Temp -Destination $s.Dest
    $entry.Placed = $true
  }
  foreach ($old in $staleLinks) {
    $backup = "$old.$PID.old"
    Move-Item -LiteralPath $old -Destination $backup
    $moved.Add([pscustomobject]@{ Dest = $old; Backup = $backup; Placed = $false })
    # Verify ownership of the file actually moved aside before committing its deletion.
    if (-not (Test-OwnedMark (Get-Mark $backup))) {
      throw "'$old' changed during the run and is no longer this project's link"
    }
  }
  foreach ($old in $staleIcons) {
    $backup = "$old.$PID.old"
    Move-Item -LiteralPath $old -Destination $backup
    $moved.Add([pscustomobject]@{ Dest = $old; Backup = $backup; Placed = $false })
  }
} catch {
  $why = $_.Exception.Message
  $moved.Reverse()
  foreach ($m in $moved) {
    if ($m.Placed) { Remove-Item -LiteralPath $m.Dest -Force -ErrorAction Ignore }
    if ($m.Backup) { Move-Item -LiteralPath $m.Backup -Destination $m.Dest -Force -ErrorAction Ignore }
  }
  Unstage
  "project-shortcuts: a link or icon could not be put in place or removed ($why); every earlier link and icon is kept"
  exit 1
}
foreach ($m in $moved) { if ($m.Backup) { Remove-Item -LiteralPath $m.Backup -Force -ErrorAction Ignore } }
foreach ($item in $plan) { "link written: $($item.Link)" }
foreach ($old in $stale) { "removed: $old" }
exit 0
