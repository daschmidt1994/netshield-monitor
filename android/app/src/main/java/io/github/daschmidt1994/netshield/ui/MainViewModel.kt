package io.github.daschmidt1994.netshield.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import io.github.daschmidt1994.netshield.NetShieldApp
import io.github.daschmidt1994.netshield.data.ApiFailure
import io.github.daschmidt1994.netshield.data.Loaded
import io.github.daschmidt1994.netshield.data.RangeKey
import io.github.daschmidt1994.netshield.data.TimeRange
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

sealed interface LoadState<out T> {
    data object Loading : LoadState<Nothing>
    data class Ready<T>(val value: Loaded<T>) : LoadState<T>
    data class Failed(val message: String) : LoadState<Nothing>
}

/** Shared app state: connection, selected time range and a generic loader with auto-refresh. */
class MainViewModel(val app: NetShieldApp) : ViewModel() {
    private val _range = MutableStateFlow(TimeRange(RangeKey.H24))
    val range: StateFlow<TimeRange> = _range.asStateFlow()
    private val _unauthorized = MutableStateFlow(false)
    val unauthorized: StateFlow<Boolean> = _unauthorized.asStateFlow()

    fun setRange(r: TimeRange) { _range.value = r }
    fun clearUnauthorized() { _unauthorized.value = false }

    /** Loads [block] now and then every [refreshMs] while the returned job is active. */
    fun <T> poll(target: MutableStateFlow<LoadState<T>>, refreshMs: Long, block: suspend () -> Loaded<T>): Job =
        viewModelScope.launch {
            while (isActive) {
                try {
                    target.value = LoadState.Ready(block())
                } catch (e: ApiFailure.Unauthorized) {
                    _unauthorized.value = true
                    target.value = LoadState.Failed("unauthorized")
                    return@launch
                } catch (e: Exception) {
                    if (target.value !is LoadState.Ready) target.value = LoadState.Failed(e.message ?: "error")
                }
                delay(refreshMs)
            }
        }

    fun refreshMsFor(r: TimeRange) = if (r.key == RangeKey.LIVE) 15_000L else 60_000L
}
