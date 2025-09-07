Get-ChildItem -Path "src_folder" -Recurse -File | Rename-Item -NewName { $_.Name.ToLower() }

Get-ChildItem -Path "src_folder" -Recurse -Directory | %{
    $NewName = $_.Name.ToLowerInvariant()
    $TempItem = Rename-Item -LiteralPath $_.FullName -NewName "a" -PassThru
    Rename-Item -LiteralPath $TempItem.FullName -NewName $NewName
}