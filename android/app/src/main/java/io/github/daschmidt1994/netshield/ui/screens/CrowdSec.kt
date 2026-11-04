package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.AlertRow
import io.github.daschmidt1994.netshield.data.CrowdsecSummary
import io.github.daschmidt1994.netshield.data.Decisions
import io.github.daschmidt1994.netshield.data.Items
import io.github.daschmidt1994.netshield.ui.LoadState
import io.github.daschmidt1994.netshield.ui.MainViewModel
import io.github.daschmidt1994.netshield.ui.components.BarRow
import io.github.daschmidt1994.netshield.ui.components.ErrorText
import io.github.daschmidt1994.netshield.ui.components.InfoText
import io.github.daschmidt1994.netshield.ui.components.Loading
import io.github.daschmidt1994.netshield.ui.components.Pill
import io.github.daschmidt1994.netshield.ui.components.SectionCard
import io.github.daschmidt1994.netshield.ui.components.StatCard
import io.github.daschmidt1994.netshield.ui.components.StatGrid
import io.github.daschmidt1994.netshield.ui.components.flag
import io.github.daschmidt1994.netshield.ui.components.fmt
import io.github.daschmidt1994.netshield.ui.components.fmtDuration
import io.github.daschmidt1994.netshield.ui.components.fmtTime
import io.github.daschmidt1994.netshield.ui.components.severityColor
import io.github.daschmidt1994.netshield.ui.theme.LocalTraffic

@Composable
fun CrowdSecScreen(vm: MainViewModel, header: @Composable () -> Unit) {
    val range by vm.range.collectAsState()
    val repo = vm.app.repository
    val refresh = vm.refreshMsFor(range)
    val sum by rememberLoad(vm, range, refreshMs = refresh) { repo.load("cs?${range.cacheKey()}", CrowdsecSummary.serializer()) { crowdsec(range.params()) } }
    val alerts by rememberLoad(vm, range, refreshMs = refresh) { repo.load("alerts?${range.cacheKey()}", Items.serializer(AlertRow.serializer())) { alerts(range.params(), 100) } }
    val dec by rememberLoad(vm, refreshMs = 120_000) { repo.load("decisions", Decisions.serializer()) { decisions() } }
    val tc = LocalTraffic.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { header() }
        item { InfoText(stringResource(R.string.alert_vs_decision)) }
        when (val s = sum) {
            is LoadState.Loading -> item { Loading() }
            is LoadState.Failed -> item { ErrorText(s.message) }
            is LoadState.Ready -> {
                val d = s.value.data
                val proxy = d.enforcement["netbird_proxy"]
                item {
                    StatGrid(listOf(
                        { m -> StatCard(stringResource(R.string.alerts), fmt(d.alerts.alerts), m, sub = "${stringResource(R.string.with_decision)}: ${fmt(d.alerts.alertsWithDecision)}") },
                        { m -> StatCard(stringResource(R.string.critical), fmt(d.alerts.bySeverity["critical"] ?: 0), m, valueColor = tc.warn) },
                        { m -> StatCard(stringResource(R.string.local_decisions), fmt(d.decisions.localActive), m) },
                        { m -> StatCard(stringResource(R.string.community), fmt(d.decisions.communityActive), m) },
                        { m -> StatCard(stringResource(R.string.blocked_by_proxy), fmt((proxy?.blocked ?: 0) + (proxy?.challenged ?: 0)), m, valueColor = tc.blocked,
                            sub = "Ban ${fmt(proxy?.blocked ?: 0)} · Captcha ${fmt(proxy?.challenged ?: 0)}") },
                        { m -> StatCard(stringResource(R.string.firewall_bouncer), "–", m, sub = stringResource(R.string.not_measurable)) },
                    ))
                }
                item {
                    SectionCard(stringResource(R.string.scenarios)) {
                        val max = d.alerts.topScenarios.maxOfOrNull { it.count } ?: 0
                        if (d.alerts.topScenarios.isEmpty()) Text(stringResource(R.string.no_data))
                        d.alerts.topScenarios.forEach { BarRow(it.scenario, it.count, max, fmt(it.count), color = tc.warn, mono = true) }
                    }
                }
            }
        }
        (dec as? LoadState.Ready)?.value?.data?.let { dd ->
            item {
                SectionCard("${stringResource(R.string.local_decisions)} (${dd.localDecisions.size})") {
                    if (dd.localDecisions.isEmpty()) Text(stringResource(R.string.no_data))
                    dd.localDecisions.forEach { x ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(x.value, fontFamily = FontFamily.Monospace)
                                Text(x.scenario ?: "", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Pill(x.type, if (x.type == "ban") tc.blocked else tc.warn)
                            Text("  ${fmtDuration(x.remainingSeconds)}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
        when (val a = alerts) {
            is LoadState.Ready -> {
                item { Text(stringResource(R.string.alerts), style = MaterialTheme.typography.titleMedium) }
                items(a.value.data.items, key = { it.id }) { al ->
                    Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Pill(al.severity, severityColor(al.severity))
                            Text("  ${fmtTime(al.created)}", style = MaterialTheme.typography.bodySmall)
                        }
                        Text(al.scenario, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodyMedium)
                        Text("${flag(al.country)} ${al.source ?: "?"} · ${al.asName ?: ""}${al.targetHost?.let { " → $it" } ?: ""}",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (al.decisions > 0) Text("${al.decisionType} · ${al.decisionDuration ?: ""}", style = MaterialTheme.typography.bodySmall, color = tc.blocked)
                        HorizontalDivider(Modifier.padding(top = 6.dp))
                    }
                }
            }
            is LoadState.Failed -> item { ErrorText(a.message) }
            else -> {}
        }
    }
}
