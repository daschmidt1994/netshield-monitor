package io.github.daschmidt1994.netshield.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/** Checks GitHub Releases for a newer signed APK of this app. */
object AppUpdate {
    private const val LATEST_URL = "https://api.github.com/repos/daschmidt1994/netshield-monitor/releases/latest"

    data class Release(val version: String, val apkUrl: String, val pageUrl: String?)

    @Serializable
    private data class GhAsset(
        val name: String = "",
        @SerialName("browser_download_url") val url: String = "",
    )

    @Serializable
    private data class GhRelease(
        @SerialName("tag_name") val tag: String = "",
        @SerialName("html_url") val html: String? = null,
        val draft: Boolean = false,
        val prerelease: Boolean = false,
        val assets: List<GhAsset> = emptyList(),
    )

    /** Latest stable release with an APK asset, or null. */
    fun parseRelease(body: String): Release? {
        val r = runCatching { json.decodeFromString(GhRelease.serializer(), body) }.getOrNull() ?: return null
        if (r.draft || r.prerelease || r.tag.isBlank()) return null
        val apk = r.assets.firstOrNull { it.name.endsWith(".apk") && it.url.isNotBlank() } ?: return null
        return Release(r.tag, apk.url, r.html)
    }

    private fun parts(v: String): List<Int>? {
        val core = v.trim().removePrefix("v").removePrefix("V").substringBefore('-').substringBefore('+')
        if (core.isEmpty()) return null
        return core.split('.').map { it.toIntOrNull() ?: return null }
    }

    /** True if [latest] is a strictly higher x.y.z than [current]; "v" prefixes and "-suffix" are ignored. */
    fun isNewer(latest: String, current: String): Boolean {
        val a = parts(latest) ?: return false
        val b = parts(current) ?: return false
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    private val client by lazy {
        OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(20, TimeUnit.SECONDS).build()
    }

    /** Network call; returns the latest release or throws on network/HTTP errors. */
    suspend fun fetchLatest(): Release? = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(LATEST_URL)
            .header("Accept", "application/vnd.github+json")
            .header("User-Agent", "netshield-monitor-android")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw IllegalStateException("GitHub HTTP ${resp.code}")
            parseRelease(resp.body?.string().orEmpty())
        }
    }
}
