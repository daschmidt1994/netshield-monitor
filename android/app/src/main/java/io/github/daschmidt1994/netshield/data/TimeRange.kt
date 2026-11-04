package io.github.daschmidt1994.netshield.data

enum class RangeKey(val apiValue: String) { LIVE("live"), H1("1h"), H24("24h"), D7("7d"), D30("30d"), CUSTOM("custom") }

data class TimeRange(val key: RangeKey, val from: Long? = null, val to: Long? = null) {
    fun params(): Map<String, String> = if (key == RangeKey.CUSTOM && from != null) {
        buildMap { put("from", from.toString()); to?.let { put("to", it.toString()) } }
    } else mapOf("range" to key.apiValue)

    fun cacheKey(): String = params().entries.joinToString("&") { "${it.key}=${it.value}" }
}
