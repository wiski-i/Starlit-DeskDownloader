$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes

function Get-BrowserAddress($Root) {
    $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
    $pending = [System.Collections.Generic.Queue[object]]::new()
    $pending.Enqueue($Root)
    $address = $null
    $fullAddress = $null
    while ($pending.Count -gt 0) {
        $element = $pending.Dequeue()
        $control = $element.Current
        if ($control.ControlType -eq [System.Windows.Automation.ControlType]::Document) {
            $pattern = $null
            if (!$fullAddress -and $element.TryGetCurrentPattern(
                    [System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                $value = $pattern.Current.Value
                if ($value -match '^https?://') { $fullAddress = $value }
            }
            continue
        }
        if ($control.ControlType -eq [System.Windows.Automation.ControlType]::Edit -and (
                $control.AcceleratorKey -eq 'Ctrl+L' -or $control.AccessKey -eq 'Ctrl+L' -or
                $control.Name -in @('Address and search bar', 'Adres ve arama çubuğu'))) {
            $pattern = $null
            if ($element.TryGetCurrentPattern(
                    [System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                if (!$control.HasKeyboardFocus) { $address = $pattern.Current.Value }
            }
        }
        $child = $walker.GetFirstChild($element)
        while ($null -ne $child) {
            $pending.Enqueue($child)
            $child = $walker.GetNextSibling($child)
        }
    }
    if ($address -match '^https?://') { return $address }
    if ($fullAddress) { return $fullAddress }
    return $address
}

try {
    $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$browserHandle)
    $process = Get-Process -Id $root.Current.ProcessId
    if ($process.ProcessName -eq 'chrome') {
        $address = Get-BrowserAddress $root
        if ($address) { [Console]::WriteLine($address) }
    }
} catch {
    exit 1
}
