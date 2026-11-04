package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.DomainRow
import io.github.daschmidt1994.netshield.data.Items
import io.github.daschmidt1994.netshield.data.Overview
import io.github.daschmidt1994.netshield.data.Timeseries
import io.github.daschmidt1994.netshield.ui.LoadState
import io.github.daschmidt1994.netshield.ui.MainViewModel
import io.github.daschmidt1994.netshield.ui.components.BarRow
import io.github.daschmidt1994.netshield.ui.components.CachedHint
import io.github.daschmidt1994.netshield.ui.components.ErrorText
import io.github.daschmidt1994.netshield.ui.components.InfoText
import io.github.daschmidt1994.netshield.ui.components.Loading
import io.github.daschmidt1994.netshield.ui.components.SectionCard
import io.github.daschmidt1994.netshield.ui.components.StatCard
import io.github.daschmidt1994.netshield.ui.components.StatGrid
import io.github.daschmidt1994.netshield.ui.components.TrafficChart
import io.github.daschmidt1994.netshield.ui.components.countryName
import io.github.daschmidt1994.netshield.ui.components.flag
import io.github.daschmidt1994.netshield.ui.components.fmt
import io.github.daschmidt1994.netshield.ui.components.severityColor
import io.github.daschmidt1994.netshield.ui.theme.LocalTraffic

@Composable
fun DashboardScreen(vm: MainViewModel, header: @Composable () -> Unit, openDomain: (String) -> Unit) {
    val range by vm.range.collectAsState()
    val repo = vm.app.repository
    val refresh = vm.refreshMsFor(range)
    val ov by rememberLoad(vm, range, refreshMs = refresh) { repo.load("overview?${range.cacheKey()}", Overview.serializer()) { overview(range.params()) } }
    val ts by rememberLoad(vm, range, refreshMs = refresh) { repo.load("ts?${range.cacheKey()}", Timeseries.serializer()) { timeseries(range.params()) } }
    val doms by rememberLoad(vm, range, refreshMs = refresh) { repo.load("domains?${range.cacheKey()}", Items.serializer(DomainRow.serializer())) { domains(range.params()) } }
    val tc = LocalTraffic.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { header() }
        when (val s = ov) {
            is LoadState.Loading -> item { Loading() }
            is LoadState.Failed -> item { ErrorText(s.message) }
            is LoadState.Ready -> {
                val o = s.value.data
                item { CachedHint(s.value.fromCache, s.value.fetchedAt) }
                item {
                    StatGrid(listOf(
                        { m -> StatCard(stringResource(R.string.requests_today), fmt(o.requestsToday), m, sub = "${fmt(o.requestsPerMinute)} ${stringResource(R.string.rpm)}") },
                        { m -> StatCard(stringResource(R.string.requests_24h), fmt(o.requests24h), m, sub = "${stringResource(R.string.in_range)}: ${fmt(o.requests.requests)}") },
                        { m -> StatCard(stringResource(R.string.visitors_est), fmt(o.visitors.value), m, sub = stringResource(R.string.visitors_hint_short)) },
                        { m -> StatCard(stringResource(R.string.active_domains), "${o.activeDomains} / ${o.knownDomains}", m) },
                        { m -> StatCard(stringResource(R.string.blocked), fmt(o.requests.blocked + o.requests.challenged), m, valueColor = tc.blocked,
                            sub = "${stringResource(R.string.cat_challenged)}: ${fmt(o.requests.challenged)}") },
                        { m -> StatCard(stringResource(R.string.alerts_24h), fmt(o.crowdsec.alerts24h), m,
                            sub = "${stringResource(R.string.critical)}: ${fmt(o.crowdsec.criticalAlerts24h)}") },
                        { m -> StatCard(stringResource(R.string.local_decisions), fmt(o.crowdsec.localActiveDecisions), m,
                            sub = "${stringResource(R.string.community)}: ${fmt(o.crowdsec.communityActiveDecisions)}") },
                        { m -> StatCard(stringResource(R.string.security_status), stringResource(when (o.securityStatus.level) {
                            "critical" -> R.string.status_critical; "warning" -> R.string.status_warning; else -> R.string.status_ok }), m,
                            valueColor = severityColor(o.securityStatus.level), sub = o.securityStatus.reasons.joinToString { it.code }.ifBlank { null }) },
                    ))
                }
                item {
                    SectionCard(stringResource(R.string.traffic)) {
                        when (val t = ts) { is LoadState.Ready -> TrafficChart(t.value.data); is LoadState.Failed -> ErrorText(t.message); else -> Loading() }
                    }
                }
                item {
                    SectionCard(stringResource(R.string.top_countries)) {
                        val max = o.topCountries.maxOfOrNull { it.requests } ?: 0
                        if (o.topCountries.isEmpty()) Text(stringResource(R.string.no_data))
                        o.topCountries.forEach { c -> BarRow("${flag(c.country)} ${countryName(c.country)}", c.requests, max, fmt(c.requests)) }
                        InfoText(stringResource(R.string.geo_approx))
                    }
                }
            }
        }
        (doms as? LoadState.Ready)?.let { d ->
            item {
                SectionCard(stringResource(R.string.domains)) {
                    val max = d.value.data.items.maxOfOrNull { it.requests } ?: 0
                    d.value.data.items.take(8).forEach { row ->
                        androidx.compose.foundation.layout.Box(Modifier.clickable { openDomain(row.host) }) {
                            BarRow(row.host, row.requests, max, fmt(row.requests), mono = true)
                        }
                    }
                }
            }
        }
    }
}
