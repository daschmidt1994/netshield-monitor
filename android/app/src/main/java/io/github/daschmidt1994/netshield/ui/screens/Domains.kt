package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.DomainDetail
import io.github.daschmidt1994.netshield.data.DomainRow
import io.github.daschmidt1994.netshield.data.Items
import io.github.daschmidt1994.netshield.ui.LoadState
import io.github.daschmidt1994.netshield.ui.MainViewModel
import io.github.daschmidt1994.netshield.ui.components.BarRow
import io.github.daschmidt1994.netshield.ui.components.CachedHint
import io.github.daschmidt1994.netshield.ui.components.ErrorText
import io.github.daschmidt1994.netshield.ui.components.InfoText
import io.github.daschmidt1994.netshield.ui.components.Loading
import io.github.daschmidt1994.netshield.ui.components.Pill
import io.github.daschmidt1994.netshield.ui.components.SectionCard
import io.github.daschmidt1994.netshield.ui.components.StatCard
import io.github.daschmidt1994.netshield.ui.components.StatGrid
import io.github.daschmidt1994.netshield.ui.components.TrafficChart
import io.github.daschmidt1994.netshield.ui.components.countryName
import io.github.daschmidt1994.netshield.ui.components.flag
import io.github.daschmidt1994.netshield.ui.components.fmt
import io.github.daschmidt1994.netshield.ui.theme.LocalTraffic

@Composable
fun DomainsScreen(vm: MainViewModel, header: @Composable () -> Unit, open: (String) -> Unit) {
    val range by vm.range.collectAsState()
    val repo = vm.app.repository
    val state by rememberLoad(vm, range, refreshMs = vm.refreshMsFor(range)) {
        repo.load("domains?${range.cacheKey()}", Items.serializer(DomainRow.serializer())) { domains(range.params()) }
    }
    val tc = LocalTraffic.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { header() }
        when (val s = state) {
            is LoadState.Loading -> item { Loading() }
            is LoadState.Failed -> item { ErrorText(s.message) }
            is LoadState.Ready -> {
                item { CachedHint(s.value.fromCache, s.value.fetchedAt) }
                items(s.value.data.items, key = { it.host }) { d ->
                    Card(Modifier.fillMaxWidth().clickable { open(d.host) }, colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
                        Column(Modifier.padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(d.host, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, maxLines = 1,
                                    overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                                d.crowdsecMode?.let { Pill(it, if (it == "enforce") tc.ok else tc.warn) }
                            }
                            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                                Metric(fmt(d.requests), stringResource(R.string.total))
                                Metric(fmt(d.blocked), stringResource(R.string.blocked))
                                Metric(fmt(d.suspicious), stringResource(R.string.cat_suspicious))
                                Metric(fmt(d.requestsPerMinute), stringResource(R.string.rpm))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Metric(value: String, label: String) = Column {
    Text(value, fontWeight = FontWeight.Bold)
    Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
fun DomainDetailScreen(vm: MainViewModel, host: String, header: @Composable () -> Unit) {
    val range by vm.range.collectAsState()
    val repo = vm.app.repository
    val state by rememberLoad(vm, range, host, refreshMs = vm.refreshMsFor(range)) {
        repo.load("domain/$host?${range.cacheKey()}", DomainDetail.serializer()) { domain(host, range.params()) }
    }
    val tc = LocalTraffic.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { header() }
        when (val s = state) {
            is LoadState.Loading -> item { Loading() }
            is LoadState.Failed -> item { ErrorText(s.message) }
            is LoadState.Ready -> {
                val d = s.value.data
                item { CachedHint(s.value.fromCache, s.value.fetchedAt) }
                d.info?.crowdsecMode?.let { mode ->
                    item {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("${stringResource(R.string.crowdsec_mode)}: "); Pill(mode, if (mode == "enforce") tc.ok else tc.warn)
                        }
                        if (mode == "observe") { Spacer(Modifier.width(4.dp)); InfoText(stringResource(R.string.observe_hint)) }
                    }
                }
                item {
                    StatGrid(listOf(
                        { m -> StatCard(stringResource(R.string.in_range), fmt(d.requests.requests), m) },
                        { m -> StatCard(stringResource(R.string.rpm), fmt(d.requestsPerMinute), m) },
                        { m -> StatCard(stringResource(R.string.visitors_est), fmt(d.visitors.value), m) },
                        { m -> StatCard(stringResource(R.string.blocked), fmt(d.requests.blocked + d.requests.challenged), m, valueColor = tc.blocked,
                            sub = if (d.requests.wouldBlockObserve > 0) "${stringResource(R.string.would_block)}: ${fmt(d.requests.wouldBlockObserve)}" else null) },
                        { m -> StatCard(stringResource(R.string.cat_suspicious), fmt(d.requests.suspicious), m, valueColor = tc.warn) },
                        { m -> StatCard(stringResource(R.string.alerts), fmt(d.crowdsec.alerts), m) },
                    ))
                }
                item { SectionCard(stringResource(R.string.traffic)) { TrafficChart(d.timeseries) } }
                item {
                    SectionCard(stringResource(R.string.status_codes)) {
                        val max = d.statuses.maxOfOrNull { it.count } ?: 0
                        d.statuses.take(8).forEach {
                            BarRow(it.status.toString(), it.count, max, fmt(it.count),
                                color = when { it.status >= 500 -> tc.blocked; it.status >= 400 -> tc.suspicious; else -> tc.visitor })
                        }
                    }
                }
                item {
                    SectionCard(stringResource(R.string.top_countries)) {
                        val max = d.countries.maxOfOrNull { it.requests } ?: 0
                        d.countries.take(10).forEach { c -> BarRow("${flag(c.country)} ${countryName(c.country)}", c.requests, max, fmt(c.requests)) }
                    }
                }
                item {
                    SectionCard(stringResource(R.string.top_paths)) {
                        val max = d.topPaths.items.maxOfOrNull { it.requests } ?: 0
                        if (d.topPaths.items.isEmpty()) Text(stringResource(R.string.no_data))
                        d.topPaths.items.forEach { BarRow(it.path, it.requests, max, fmt(it.requests), mono = true) }
                    }
                }
                item {
                    SectionCard(stringResource(R.string.suspicious_paths)) {
                        val max = d.suspiciousPaths.items.maxOfOrNull { it.requests } ?: 0
                        if (d.suspiciousPaths.items.isEmpty()) Text(stringResource(R.string.no_data))
                        d.suspiciousPaths.items.forEach { BarRow(it.path, it.requests, max, fmt(it.requests), color = tc.suspicious, mono = true) }
                    }
                }
                if (d.crowdsec.topScenarios.isNotEmpty()) item {
                    SectionCard(stringResource(R.string.scenarios)) {
                        val max = d.crowdsec.topScenarios.maxOf { it.count }
                        d.crowdsec.topScenarios.forEach { BarRow(it.scenario, it.count, max, fmt(it.count), color = tc.warn, mono = true) }
                    }
                }
            }
        }
    }
}
