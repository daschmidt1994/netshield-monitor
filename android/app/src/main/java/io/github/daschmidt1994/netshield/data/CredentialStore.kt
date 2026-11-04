package io.github.daschmidt1994.netshield.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

private val Context.dataStore by preferencesDataStore("netshield")

data class Connection(val baseUrl: String, val token: String)

data class AppPrefs(
    val notifyEnabled: Boolean = true,
    val notifyCriticalOnly: Boolean = false,
    val notifyBackendOffline: Boolean = true,
    val theme: String = "system",
)

/**
 * Stores the backend URL in DataStore and the API token encrypted with an AES-256-GCM key that lives
 * in the Android Keystore (never leaves secure hardware where available, not included in backups).
 */
class CredentialStore(private val context: Context) {
    private object Keys {
        val url = stringPreferencesKey("url")
        val token = stringPreferencesKey("token_enc")
        val lastNotification = longPreferencesKey("last_notification_id")
        val lastOfflineNotice = longPreferencesKey("last_offline_notice")
        val notifyEnabled = booleanPreferencesKey("notify_enabled")
        val notifyCriticalOnly = booleanPreferencesKey("notify_critical_only")
        val notifyOffline = booleanPreferencesKey("notify_offline")
        val theme = stringPreferencesKey("theme")
    }

    val connection: Flow<Connection?> = context.dataStore.data.map { p ->
        val url = p[Keys.url]
        val enc = p[Keys.token]
        if (url.isNullOrBlank() || enc.isNullOrBlank()) null else runCatching { Connection(url, decrypt(enc)) }.getOrNull()
    }

    val prefs: Flow<AppPrefs> = context.dataStore.data.map { p ->
        AppPrefs(
            notifyEnabled = p[Keys.notifyEnabled] ?: true,
            notifyCriticalOnly = p[Keys.notifyCriticalOnly] ?: false,
            notifyBackendOffline = p[Keys.notifyOffline] ?: true,
            theme = p[Keys.theme] ?: "system",
        )
    }

    suspend fun current(): Connection? = connection.first()

    suspend fun save(url: String, token: String) {
        context.dataStore.edit {
            it[Keys.url] = url
            it[Keys.token] = encrypt(token)
            it.remove(Keys.lastNotification)
        }
    }

    suspend fun clear() = context.dataStore.edit { it.remove(Keys.url); it.remove(Keys.token); it.remove(Keys.lastNotification) }

    suspend fun lastNotificationId(): Long? = context.dataStore.data.first()[Keys.lastNotification]
    suspend fun setLastNotificationId(id: Long) = context.dataStore.edit { it[Keys.lastNotification] = id }
    suspend fun lastOfflineNotice(): Long = context.dataStore.data.first()[Keys.lastOfflineNotice] ?: 0
    suspend fun setLastOfflineNotice(ts: Long) = context.dataStore.edit { it[Keys.lastOfflineNotice] = ts }

    suspend fun updatePrefs(transform: (AppPrefs) -> AppPrefs) {
        val next = transform(prefs.first())
        context.dataStore.edit {
            it[Keys.notifyEnabled] = next.notifyEnabled
            it[Keys.notifyCriticalOnly] = next.notifyCriticalOnly
            it[Keys.notifyOffline] = next.notifyBackendOffline
            it[Keys.theme] = next.theme
        }
    }

    // --- Keystore crypto -------------------------------------------------------------
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return gen.generateKey()
    }

    private fun encrypt(plain: String): String {
        val c = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
        val out = c.iv + c.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(out, Base64.NO_WRAP)
    }

    private fun decrypt(enc: String): String {
        val raw = Base64.decode(enc, Base64.NO_WRAP)
        val c = Cipher.getInstance(TRANSFORMATION)
        c.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw, 0, 12))
        return String(c.doFinal(raw, 12, raw.size - 12), Charsets.UTF_8)
    }

    companion object {
        private const val ALIAS = "netshield_token_key"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
