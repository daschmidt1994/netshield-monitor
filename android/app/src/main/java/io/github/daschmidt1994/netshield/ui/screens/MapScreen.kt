package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.CountryRow
import io.github.daschmidt1994.netshield.data.DomainRow
import io.github.daschmidt1994.netshield.data.Items
import io.github.daschmidt1994.netshield.ui.LoadState
import io.github.daschmidt1994.netshield.ui.MainViewModel
import io.github.daschmidt1994.netshield.ui.components.BarRow
import io.github.daschmidt1994.netshield.ui.components.ErrorText
import io.github.daschmidt1994.netshield.ui.components.InfoText
import io.github.daschmidt1994.netshield.ui.components.Loading
import io.github.daschmidt1994.netshield.ui.components.SectionCard
import io.github.daschmidt1994.netshield.ui.components.WorldMap
import io.github.daschmidt1994.netshield.ui.components.countryName
import io.github.daschmidt1994.netshield.ui.components.flag
import io.github.daschmidt1994.netshield.ui.components.fmt
import io.github.daschmidt1994.netshield.ui.theme.LocalTraffic

private enum class Metric { TOTAL, ALLOWED, BLOCKED }

@Composable
fun MapScreen(vm: MainViewModel, header: @Composable () -> Unit) {
    val range by vm.range.collectAsState()
    val repo = vm.app.repository
    var host by remember { mutableStateOf<String?>(null) }
    var metric by remember { mutableStateOf(Metric.TOTAL) }
    var selected by remember { mutableStateOf<String?>(null) }
    val doms by rememberLoad(vm, range, refreshMs = 300_000) {
        repo.load("domains?${range.cacheKey()}", Items.serializer(DomainRow.serializer())) { domains(range.params()) }
    }
    val state by rememberLoad(vm, range, host, refreshMs = vm.refreshMsFor(range)) {
        repo.load("countries?${range.cacheKey()}&host=${host ?: ""}", Items.serializer(CountryRow.serializer())) { countries(range.params(), host) }
    }
    val tc = LocalTraffic.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { header() }
        item {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(host == null, { host = null }, { Text(stringResource(R.string.all_domains)) })
                (doms as? LoadState.Ready)?.value?.data?.items?.forEach { d ->
                    FilterChip(host == d.host, { host = d.host }, { Text(d.host) })
                }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(metric == Metric.TOTAL, { metric = Metric.TOTAL }, { Text(stringResource(R.string.total)) })
                FilterChip(metric == Metric.ALLOWED, { metric = Metric.ALLOWED }, { Text(stringResource(R.string.allowed)) })
                FilterChip(metric == Metric.BLOCKED, { metric = Metric.BLOCKED }, { Text(stringResource(R.string.blocked)) })
            }
        }
        when (val s = state) {
            is LoadState.Loading -> item { Loading() }
            is LoadState.Failed -> item { ErrorText(s.message) }
            is LoadState.Ready -> {
                val rows = s.value.data.items
                val values = rows.filter { it.country != null }.associate {
                    it.country!! to when (metric) { Metric.TOTAL -> it.requests; Metric.ALLOWED -> it.allowed; Metric.BLOCKED -> it.blocked }
                }
                item {
                    SectionCard(stringResource(R.string.map)) {
                        WorldMap(values, if (metric == Metric.BLOCKED) tc.blocked else tc.visitor) { selected = it }
                        selected?.let { cc ->
                            val r = rows.firstOrNull { it.country == cc }
                            Text("${flag(cc)} ${countryName(cc)}: ${fmt(r?.requests ?: 0)} · ${stringResource(R.string.allowed)} ${fmt(r?.allowed ?: 0)} · ${stringResource(R.string.blocked)} ${fmt(r?.blocked ?: 0)}")
                        }
                        InfoText(stringResource(R.string.geo_approx))
                    }
                }
                item {
                    SectionCard(stringResource(R.string.top_countries)) {
                        val max = rows.maxOfOrNull { it.requests } ?: 0
                        rows.take(30).forEach { c ->
                            BarRow("${flag(c.country)} ${countryName(c.country)}", c.requests, max,
                                "${fmt(c.requests)} / ${fmt(c.blocked)}")
                        }
                    }
                }
            }
        }
    }
}
