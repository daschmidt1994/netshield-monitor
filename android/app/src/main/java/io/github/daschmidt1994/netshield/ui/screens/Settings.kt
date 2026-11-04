package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.AppPrefs
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
    val tc = LocalTraffic.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            SectionCard(stringResource(R.string.connection)) {
                Text(conn?.baseUrl ?: "–", fontFamily = FontFamily.Monospace)
                (sources as? LoadState.Ready)?.value?.data?.version?.let { Text("Backend v$it", style = MaterialTheme.typography.bodySmall) }
                OutlinedButton(onClick = { scope.launch { store.clear(); vm.app.repository.clearCache(); onLogout() } },
                    modifier = Modifier.padding(top = 8.dp)) { Text(stringResource(R.string.disconnect)) }
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

@Composable
private fun Toggle(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Switch(value, onChange)
    }
}
