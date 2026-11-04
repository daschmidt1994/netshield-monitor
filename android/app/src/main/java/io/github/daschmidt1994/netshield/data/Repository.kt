package io.github.daschmidt1994.netshield.data

import io.github.daschmidt1994.netshield.BuildConfig
import io.github.daschmidt1994.netshield.data.db.CacheDao
import io.github.daschmidt1994.netshield.data.db.CachedResponse
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit

val json = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true }

sealed class ApiFailure(message: String) : Exception(message) {
    class Unauthorized : ApiFailure("unauthorized")
    class Network(cause: Throwable) : ApiFailure(cause.message ?: "network error")
    class Server(val code: Int) : ApiFailure("HTTP $code")
}

/** Result of a load: data plus whether it came from the offline cache. */
data class Loaded<T>(val data: T, val fromCache: Boolean, val fetchedAt: Long, val error: ApiFailure? = null)

fun buildService(conn: Connection): NetShieldService {
    val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            chain.proceed(
                chain.request().newBuilder()
                    .header("Authorization", "Bearer ${conn.token}")
                    .header("User-Agent", "NetShield-Android/${BuildConfig.VERSION_NAME}")
                    .build()
            )
        }
        .build()
    val base = if (conn.baseUrl.endsWith("/")) conn.baseUrl else conn.baseUrl + "/"
    return Retrofit.Builder()
        .baseUrl(base)
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(NetShieldService::class.java)
}

class Repository(private val store: CredentialStore, private val cache: CacheDao) {
    @Volatile private var service: NetShieldService? = null
    @Volatile private var serviceFor: Connection? = null

    private suspend fun svc(): NetShieldService {
        val conn = store.current() ?: throw ApiFailure.Unauthorized()
        if (service == null || serviceFor != conn) {
            service = buildService(conn); serviceFor = conn
        }
        return service!!
    }

    suspend fun <T> load(key: String, serializer: KSerializer<T>, call: suspend NetShieldService.() -> T): Loaded<T> {
        return try {
            val data = svc().call()
            val now = System.currentTimeMillis()
            cache.put(CachedResponse(key, json.encodeToString(serializer, data), now))
            Loaded(data, fromCache = false, fetchedAt = now)
        } catch (e: Exception) {
            val failure = e.toFailure()
            if (failure is ApiFailure.Unauthorized) throw failure
            val cached = cache.get(key) ?: throw failure
            Loaded(json.decodeFromString(serializer, cached.json), fromCache = true, fetchedAt = cached.fetchedAt, error = failure)
        }
    }

    suspend fun <T> fresh(call: suspend NetShieldService.() -> T): T = try { svc().call() } catch (e: Exception) { throw e.toFailure() }

    suspend fun clearCache() = cache.clear()
}

fun Throwable.toFailure(): ApiFailure = when (this) {
    is ApiFailure -> this
    is HttpException -> if (code() == 401 || code() == 403) ApiFailure.Unauthorized() else ApiFailure.Server(code())
    is IOException -> ApiFailure.Network(this)
    else -> ApiFailure.Network(this)
}

/** Validates URL + token before saving them. */
suspend fun testConnection(url: String, token: String): Result<Health> = runCatching {
    val s = buildService(Connection(url, token))
    s.sources() // requires a valid token
    s.health()
}.recoverCatching { throw it.toFailure() }
