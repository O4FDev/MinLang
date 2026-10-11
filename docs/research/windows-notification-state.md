# First use of a Windows notification identity

The actual Windows 11 Enterprise evaluation guest rejected the maintained notification fixture with kind 7 and HRESULT 0x80070490 at ToastNotifier.get_Setting. The failure happened before persist_notice and Show.

The isolated diagnostic used the same user SID as the console desktop. Explorer and WpnUserService were running in session 1 and the notification database existed. The same result occurred from the desktop and WinRM sessions. Explorer and PowerShell notifier identities also returned setting-not-found, and SHChangeNotify did not initialize the owned identity.

For the newly registered owned Minyar identity, persist_notice and the real OS Show both succeeded. Immediately afterwards the same owned notifier's get_Setting succeeded; unrelated built-in identities still returned setting-not-found. This distinguishes an absent per-identity record from a disabled setting.

The provider now permits only ERROR_NOT_FOUND from the preflight setting lookup to reach the existing persistence and Show path. Existing disabled settings still return access denied. All other lookup failures and every persistence or Show failure retain their original HRESULT. Success means the OS accepted the notification; asynchronous delivery failures remain available through the existing Failed handler and status API.

The maintained real-OS fixture and its strict success-or-permission-denied assertion remain unchanged. Raw evidence is retained under /home/user/minyar-overnight/windows/shared/evidence/notify-context.log and the matching source hash, interactive context, and WinRM context records. Actual verification of this source change is recorded separately; the initial diagnostics are red evidence, not a green result.
