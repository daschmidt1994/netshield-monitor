package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.remember
import io.github.daschmidt1994.netshield.data.Loaded
import io.github.daschmidt1994.netshield.ui.LoadState
import io.github.daschmidt1994.netshield.ui.MainViewModel
import kotlinx.coroutines.flow.MutableStateFlow

/** Screen-level loader backed by the ViewModel scope; restarts when [keys] change. */
@Composable
fun <T> rememberLoad(vm: MainViewModel, vararg keys: Any?, refreshMs: Long = 60_000L, block: suspend () -> Loaded<T>): State<LoadState<T>> {
    val flow = remember(*keys) { MutableStateFlow<LoadState<T>>(LoadState.Loading) }
    DisposableEffect(*keys) {
        val job = vm.poll(flow, refreshMs, block)
        onDispose { job.cancel() }
    }
    return flow.collectAsState()
}
