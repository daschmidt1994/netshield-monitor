package io.github.daschmidt1994.netshield

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import io.github.daschmidt1994.netshield.data.AppPrefs
import io.github.daschmidt1994.netshield.ui.NetShieldRoot
import io.github.daschmidt1994.netshield.ui.theme.NetShieldTheme

class MainActivity : ComponentActivity() {
    private val askNotifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as NetShieldApp
        if (Build.VERSION.SDK_INT >= 33) askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        setContent {
            val prefs by app.store.prefs.collectAsState(initial = AppPrefs())
            NetShieldTheme(themeSetting = prefs.theme) {
                NetShieldRoot(app)
            }
        }
    }
}
