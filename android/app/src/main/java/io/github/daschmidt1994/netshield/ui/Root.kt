package io.github.daschmidt1994.netshield.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.DateRangePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDateRangePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import io.github.daschmidt1994.netshield.NetShieldApp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.Connection
import io.github.daschmidt1994.netshield.data.RangeKey
import io.github.daschmidt1994.netshield.data.TimeRange
import io.github.daschmidt1994.netshield.ui.components.RangeSelector
import io.github.daschmidt1994.netshield.ui.screens.CrowdSecScreen
import io.github.daschmidt1994.netshield.ui.screens.DashboardScreen
import io.github.daschmidt1994.netshield.ui.screens.DomainDetailScreen
import io.github.daschmidt1994.netshield.ui.screens.DomainsScreen
import io.github.daschmidt1994.netshield.ui.screens.MapScreen
import io.github.daschmidt1994.netshield.ui.screens.SettingsScreen
import io.github.daschmidt1994.netshield.ui.screens.SetupScreen
import java.net.URLDecoder
import java.net.URLEncoder

private data class Tab(val route: String, val label: Int, val icon: ImageVector)

private val TABS = listOf(
    Tab("dashboard", R.string.nav_dashboard, Icons.Filled.Home),
    Tab("domains", R.string.nav_domains, Icons.Filled.List),
    Tab("map", R.string.nav_map, Icons.Filled.Place),
    Tab("crowdsec", R.string.nav_crowdsec, Icons.Filled.Warning),
    Tab("settings", R.string.nav_settings, Icons.Filled.Settings),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NetShieldRoot(app: NetShieldApp) {
    val conn by app.store.connection.collectAsState(initial = Connection("loading", ""))
    if (conn?.baseUrl == "loading") return
    var setupDone by remember { mutableStateOf(false) }
    if (conn == null && !setupDone) {
        Scaffold { pad -> Column(Modifier.padding(pad)) { SetupScreen(app) { setupDone = true } } }
        return
    }
    val vm: MainViewModel = viewModel(factory = viewModelFactory { initializer { MainViewModel(app) } })
    val unauthorized by vm.unauthorized.collectAsState()
    LaunchedEffect(unauthorized) {
        if (unauthorized) { app.store.clear(); vm.clearUnauthorized(); setupDone = false }
    }
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route ?: "dashboard"
    val range by vm.range.collectAsState()
    var showPicker by remember { mutableStateOf(false) }
    val header: @Composable () -> Unit = {
        RangeSelector(range.key) { k -> if (k == RangeKey.CUSTOM) showPicker = true else vm.setRange(TimeRange(k)) }
    }
    if (showPicker) {
        val state = rememberDateRangePickerState()
        DatePickerDialog(onDismissRequest = { showPicker = false }, confirmButton = {
            TextButton(onClick = {
                val s = state.selectedStartDateMillis; val e = state.selectedEndDateMillis
                if (s != null) vm.setRange(TimeRange(RangeKey.CUSTOM, s / 1000, ((e ?: s) + 86_400_000) / 1000))
                showPicker = false
            }) { Text(stringResource(android.R.string.ok)) }
        }) { DateRangePicker(state, modifier = Modifier.padding(top = 8.dp)) }
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (route.startsWith("domain/")) URLDecoder.decode(entry?.arguments?.getString("host") ?: "", "UTF-8") else stringResource(R.string.app_name)) },
                navigationIcon = {
                    if (route.startsWith("domain/")) IconButton(onClick = { nav.popBackStack() }) { Icon(Icons.Filled.ArrowBack, contentDescription = null) }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                TABS.forEach { t ->
                    NavigationBarItem(
                        selected = route == t.route || (t.route == "domains" && route.startsWith("domain/")),
                        onClick = { nav.navigate(t.route) { popUpTo("dashboard") { saveState = true }; launchSingleTop = true; restoreState = true } },
                        icon = { Icon(t.icon, contentDescription = null) },
                        label = { Text(stringResource(t.label)) },
                    )
                }
            }
        },
    ) { pad ->
        NavHost(nav, startDestination = "dashboard", modifier = Modifier.padding(pad)) {
            val open: (String) -> Unit = { nav.navigate("domain/" + URLEncoder.encode(it, "UTF-8")) }
            composable("dashboard") { DashboardScreen(vm, header, open) }
            composable("domains") { DomainsScreen(vm, header, open) }
            composable("domain/{host}", arguments = listOf(navArgument("host") { type = NavType.StringType })) {
                DomainDetailScreen(vm, URLDecoder.decode(it.arguments?.getString("host") ?: "", "UTF-8"), header)
            }
            composable("map") { MapScreen(vm, header) }
            composable("crowdsec") { CrowdSecScreen(vm, header) }
            composable("settings") { SettingsScreen(vm) { setupDone = false } }
        }
    }
}
