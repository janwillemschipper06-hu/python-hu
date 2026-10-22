<#
    Ping Tool - simpele grafische ping-tool (Windows Forms)

    Starten:
        powershell -ExecutionPolicy Bypass -File ping_tool.ps1
    of met PowerShell 7:
        pwsh -ExecutionPolicy Bypass -File ping_tool.ps1

    Gebruik:
        1. Vul een hostname of IP-adres in (bijv. google.com of 8.8.8.8)
        2. Kies hoeveel pings je wilt versturen (standaard 4)
        3. Klik op "Ping" of druk op Enter in het tekstvak
    De uitvoer verschijnt per reply in het grote tekstvak, met onderaan
    een samenvatting (verzonden / ontvangen / verlies / gemiddelde tijd).

    Voor testen zonder GUI:
        . .\ping_tool.ps1 -GeenGui      (dot-sourcen laadt alleen de functies)
        Invoke-PingTest -Hostname localhost -Aantal 2
#>

param(
    # Met -GeenGui worden alleen de functies geladen (handig voor testen)
    [switch]$GeenGui
)

# Pingt een host een aantal keer. Voor elke regel uitvoer wordt het
# scriptblock $OpRegel aangeroepen (zo kan de GUI direct bijwerken).
# Geeft alle regels ook terug als lijst.
function Invoke-PingTest {
    param(
        [Parameter(Mandatory)] [string]$Hostname,
        [int]$Aantal = 4,
        [int]$TimeoutMs = 2000,
        [scriptblock]$OpRegel = {}
    )

    $regels = New-Object System.Collections.Generic.List[string]
    $schrijf = {
        param($tekst)
        $regels.Add($tekst)
        & $OpRegel $tekst
    }

    $Hostname = $Hostname.Trim()
    if ([string]::IsNullOrWhiteSpace($Hostname)) {
        & $schrijf "Fout: vul eerst een hostname of IP-adres in."
        return $regels
    }

    & $schrijf "Pingen naar $Hostname met $Aantal ping(s)..."
    & $schrijf ""

    $ping = New-Object System.Net.NetworkInformation.Ping
    $ontvangen = 0
    $tijden = @()

    try {
        for ($i = 1; $i -le $Aantal; $i++) {
            try {
                $antwoord = $ping.Send($Hostname, $TimeoutMs)
                if ($antwoord.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {
                    $ontvangen++
                    $tijden += $antwoord.RoundtripTime
                    & $schrijf ("Antwoord van {0}: tijd={1} ms" -f $antwoord.Address, $antwoord.RoundtripTime)
                }
                elseif ($antwoord.Status -eq [System.Net.NetworkInformation.IPStatus]::TimedOut) {
                    & $schrijf "Time-out: geen antwoord binnen $TimeoutMs ms."
                }
                else {
                    & $schrijf "Geen antwoord: $($antwoord.Status)"
                }
            }
            catch [System.Net.NetworkInformation.PingException] {
                # Gebeurt meestal als de hostname niet bestaat (DNS-fout)
                $reden = if ($_.Exception.InnerException) { $_.Exception.InnerException.Message } else { $_.Exception.Message }
                & $schrijf "Fout: host '$Hostname' niet gevonden of niet bereikbaar ($reden)"
                break   # verder pingen heeft geen zin
            }

            # Even wachten tussen pings (niet na de laatste)
            if ($i -lt $Aantal) { Start-Sleep -Milliseconds 500 }
        }
    }
    finally {
        $ping.Dispose()
    }

    # Samenvatting
    $verloren = $Aantal - $ontvangen
    $verliesProcent = [math]::Round(($verloren / $Aantal) * 100)
    & $schrijf ""
    & $schrijf "--- Samenvatting voor $Hostname ---"
    & $schrijf "Verzonden: $Aantal, Ontvangen: $ontvangen, Verloren: $verloren ($verliesProcent% verlies)"
    if ($tijden.Count -gt 0) {
        $gemiddeld = [math]::Round(($tijden | Measure-Object -Average).Average, 1)
        $min = ($tijden | Measure-Object -Minimum).Minimum
        $max = ($tijden | Measure-Object -Maximum).Maximum
        & $schrijf "Tijd: minimum=$min ms, maximum=$max ms, gemiddeld=$gemiddeld ms"
    }
    else {
        & $schrijf "Geen antwoorden ontvangen, dus geen gemiddelde tijd."
    }

    return $regels
}

function Show-PingGui {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()

    # Hoofdvenster
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Ping Tool"
    $form.Size = New-Object System.Drawing.Size(620, 480)
    $form.StartPosition = "CenterScreen"
    $form.MinimumSize = New-Object System.Drawing.Size(500, 300)

    # Label + tekstvak voor de hostname
    $lblHost = New-Object System.Windows.Forms.Label
    $lblHost.Text = "Hostname / IP:"
    $lblHost.Location = New-Object System.Drawing.Point(10, 15)
    $lblHost.AutoSize = $true
    $form.Controls.Add($lblHost)

    $txtHost = New-Object System.Windows.Forms.TextBox
    $txtHost.Location = New-Object System.Drawing.Point(110, 12)
    $txtHost.Width = 220
    $txtHost.Text = "google.com"
    $form.Controls.Add($txtHost)

    # Aantal pings
    $lblAantal = New-Object System.Windows.Forms.Label
    $lblAantal.Text = "Aantal:"
    $lblAantal.Location = New-Object System.Drawing.Point(345, 15)
    $lblAantal.AutoSize = $true
    $form.Controls.Add($lblAantal)

    $numAantal = New-Object System.Windows.Forms.NumericUpDown
    $numAantal.Location = New-Object System.Drawing.Point(395, 12)
    $numAantal.Width = 60
    $numAantal.Minimum = 1
    $numAantal.Maximum = 100
    $numAantal.Value = 4
    $form.Controls.Add($numAantal)

    # Ping-knop
    $btnPing = New-Object System.Windows.Forms.Button
    $btnPing.Text = "Ping"
    $btnPing.Location = New-Object System.Drawing.Point(470, 10)
    $btnPing.Width = 120
    $form.Controls.Add($btnPing)

    # Groot uitvoer-tekstvak (alleen lezen)
    $txtUitvoer = New-Object System.Windows.Forms.TextBox
    $txtUitvoer.Location = New-Object System.Drawing.Point(10, 45)
    $txtUitvoer.Size = New-Object System.Drawing.Size(582, 385)
    $txtUitvoer.Multiline = $true
    $txtUitvoer.ReadOnly = $true
    $txtUitvoer.ScrollBars = "Vertical"
    $txtUitvoer.Font = New-Object System.Drawing.Font("Consolas", 10)
    $txtUitvoer.BackColor = [System.Drawing.Color]::White
    $txtUitvoer.Anchor = "Top, Bottom, Left, Right"
    $form.Controls.Add($txtUitvoer)

    # Wat er gebeurt als je op Ping klikt
    $startPing = {
        $btnPing.Enabled = $false
        $txtUitvoer.Clear()
        # Per regel tekst toevoegen en de GUI laten bijwerken (DoEvents)
        $opRegel = {
            param($tekst)
            $txtUitvoer.AppendText($tekst + [Environment]::NewLine)
            [System.Windows.Forms.Application]::DoEvents()
        }
        try {
            Invoke-PingTest -Hostname $txtHost.Text -Aantal ([int]$numAantal.Value) -OpRegel $opRegel | Out-Null
        }
        catch {
            $txtUitvoer.AppendText("Onverwachte fout: $($_.Exception.Message)" + [Environment]::NewLine)
        }
        finally {
            $btnPing.Enabled = $true
        }
    }

    $btnPing.Add_Click($startPing)

    # Enter in het hostname-tekstvak = ping
    $txtHost.Add_KeyDown({
        param($sender, $e)
        if ($e.KeyCode -eq [System.Windows.Forms.Keys]::Enter) {
            $e.SuppressKeyPress = $true   # geen 'ding'-geluid
            if ($btnPing.Enabled) { & $startPing }
        }
    })

    [void]$form.ShowDialog()
    $form.Dispose()
}

# Alleen de GUI starten als het script normaal wordt uitgevoerd
if (-not $GeenGui) {
    Show-PingGui
}
