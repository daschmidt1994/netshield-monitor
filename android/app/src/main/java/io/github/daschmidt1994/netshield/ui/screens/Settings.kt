package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.BuildConfig
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.AppPrefs
import io.github.daschmidt1994.netshield.data.AppUpdate
import io.github.daschmidt1994.netshield.data.Sources
import io.github.daschmidt1994.netshield.data.db.StoredNotification
import io.github.daschmidt1994.netshield.ui.LoadState
import io.github.daschmidt1994.netshield.ui.MainViewModel
import io.github.daschmidt1994.netshield.ui.components.ErrorText
import io.github.daschmidt1994.netshield.ui.components.InfoText
import io.github.daschmidt1994.netshield.ui.components.Pill
import io.github.daschmidt1994.netshield.ui.components.SectionCard
import io.github.daschmidt1994.netshield.ui.components.fmtTime
import io.github.daschmidt1994.netshield.ui.components.severityColor
import io.github.daschmidt1994.netshield.ui.theme.LocalTraffic
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(vm: MainViewModel, onLogout: () -> Unit) {
    val store = vm.app.store
    val prefs by store.prefs.collectAsState(initial = AppPrefs())
    val conn by store.connection.collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    val sources by rememberLoad(vm, refreshMs = 60_000) { vm.app.repository.load("sources", Sources.serializer()) { sources() } }
    var notes by remember { mutableStateOf<List<StoredNotification>>(emptyList()) }
    LaunchedEffect(Unit) { notes = vm.app.database.cache().notifications(30) }
    var update by remember { mutableStateOf<UpdateUi>(UpdateUi.Idle) }
    val uriHandler = LocalUriHandler.current
    val tc = LocalTraffic.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            SectionCard(stringResource(R.string.connection)) {
                Text(conn?.baseUrl ?: "–", fontFamily = FontFamily.Monospace)
                OutlinedButton(onClick = { scope.launch { store.clear(); vm.app.repository.clearCache(); onLogout() } },
                    modifier = Modifier.padding(top = 8.dp)) { Text(stringResource(R.string.disconnect)) }
            }
        }
        item {
            SectionCard(stringResource(R.string.app_version_title)) {
                val current = BuildConfig.VERSION_NAME.removePrefix("v")
                Text(stringResource(R.string.app_version_line, current, BuildConfig.VERSION_CODE))
                (sources as? LoadState.Ready)?.value?.data?.version?.takeIf { it.isNotBlank() }?.let {
                    Text(stringResource(R.string.server_version_line, it), style = MaterialTheme.typography.bodySmall)
                }
                when (val u = update) {
                    UpdateUi.Idle -> {}
                    UpdateUi.Checking -> InfoText(stringResource(R.string.update_checking))
                    UpdateUi.Current -> InfoText(stringResource(R.string.update_current))
                    is UpdateUi.Failed -> ErrorText(stringResource(R.string.update_failed, u.message))
                    is UpdateUi.Available -> {
                        Text(stringResource(R.string.update_available, u.release.version.removePrefix("v")),
                            style = MaterialTheme.typography.bodyMedium)
                        Button(onClick = { uriHandler.openUri(u.release.apkUrl) }, modifier = Modifier.padding(top = 6.dp)) {
                            Text(stringResource(R.string.update_download))
                        }
                        InfoText(stringResource(R.string.update_install_hint))
                    }
                }
                OutlinedButton(
                    onClick = {
                        update = UpdateUi.Checking
                        scope.launch {
                            update = runCatching { AppUpdate.fetchLatest() }.fold(
                                onSuccess = { r -> if (r != null && AppUpdate.isNewer(r.version, current)) UpdateUi.Available(r) else UpdateUi.Current },
                                onFailure = { e -> UpdateUi.Failed(e.message ?: e::class.java.simpleName) },
                            )
                        }
                    },
                    enabled = update != UpdateUi.Checking,
                    modifier = Modifier.padding(top = 8.dp),
                ) { Text(stringResource(R.string.update_check)) }
            }
        }
        item {
            SectionCard(stringResource(R.string.notifications)) {
                Toggle(stringResource(R.string.notify_enabled), prefs.notifyEnabled) { v -> scope.launch { store.updatePrefs { it.copy(notifyEnabled = v) } } }
                Toggle(stringResource(R.string.notify_critical_only), prefs.notifyCriticalOnly) { v -> scope.launch { store.updatePrefs { it.copy(notifyCriticalOnly = v) } } }
                Toggle(stringResource(R.string.notify_backend), prefs.notifyBackendOffline) { v -> scope.launch { store.updatePrefs { it.copy(notifyBackendOffline = v) } } }
                InfoText(stringResource(R.string.notify_hint))
            }
        }
        item {
            SectionCard(stringResource(R.string.theme)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("system" to R.string.theme_system, "light" to R.string.theme_light, "dark" to R.string.theme_dark).forEach { (k, l) ->
                        FilterChip(prefs.theme == k, { scope.launch { store.updatePrefs { it.copy(theme = k) } } }, { Text(stringResource(l)) })
                    }
                }
            }
        }
        item {
            SectionCard(stringResource(R.string.sources)) {
                when (val s = sources) {
                    is LoadState.Ready -> s.value.data.sources.forEach { src ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(src.name, fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                            val st = if (!src.configured) "—" else src.status ?: "?"
                            Pill(st, when (st) { "ok" -> tc.ok; "error" -> tc.blocked; "backfill" -> tc.visitor; else -> MaterialTheme.colorScheme.onSurfaceVariant })
                        }
                    }
                    is LoadState.Failed -> ErrorText(s.message)
                    else -> {}
                }
            }
        }
        item {
            SectionCard(stringResource(R.string.recent_notifications)) {
                if (notes.isEmpty()) Text(stringResource(R.string.no_data))
                notes.forEach { n ->
                    Column(Modifier.padding(vertical = 4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) { Pill(n.severity, severityColor(n.severity)); Text("  ${fmtTime(n.ts)}", style = MaterialTheme.typography.bodySmall) }
                        Text(n.title, style = MaterialTheme.typography.bodyMedium)
                        Text(n.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

private sealed interface UpdateUi {
    data object Idle : UpdateUi
    data object Checking : UpdateUi
    data object Current : UpdateUi
    data class Available(val release: AppUpdate.Release) : UpdateUi
    data class Failed(val message: String) : UpdateUi
}

@Composable
private fun Toggle(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Switch(value, onChange)
    }
}
