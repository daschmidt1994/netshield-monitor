package io.github.daschmidt1994.netshield.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import io.github.daschmidt1994.netshield.NetShieldApp
import io.github.daschmidt1994.netshield.R
import io.github.daschmidt1994.netshield.data.ApiFailure
import io.github.daschmidt1994.netshield.data.testConnection
import io.github.daschmidt1994.netshield.ui.components.ErrorText
import io.github.daschmidt1994.netshield.ui.components.InfoText
import kotlinx.coroutines.launch

@Composable
fun SetupScreen(app: NetShieldApp, onDone: () -> Unit) {
    var url by remember { mutableStateOf("https://") }
    var token by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val errUnauthorized = stringResource(R.string.setup_error_token)
    val errNetwork = stringResource(R.string.setup_error_network)
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium)
        Text(stringResource(R.string.setup_intro), style = MaterialTheme.typography.bodyMedium)
        OutlinedTextField(url, { url = it.trim() }, label = { Text(stringResource(R.string.setup_url)) }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri), modifier = Modifier.fillMaxWidth())
        OutlinedTextField(token, { token = it.trim() }, label = { Text(stringResource(R.string.setup_token)) }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        if (url.startsWith("http://")) InfoText(stringResource(R.string.setup_http_warning))
        error?.let { ErrorText(it) }
        Button(enabled = !busy && url.length > 10 && token.startsWith("nsm_"), modifier = Modifier.fillMaxWidth(), onClick = {
            busy = true; error = null
            scope.launch {
                testConnection(url, token).onSuccess {
                    app.store.save(url.trimEnd('/'), token)
                    app.repository.clearCache()
                    onDone()
                }.onFailure {
                    error = when (it) { is ApiFailure.Unauthorized -> errUnauthorized; is ApiFailure.Server -> "HTTP ${it.code}"; else -> "$errNetwork (${it.message})" }
                }
                busy = false
            }
        }) { Text(stringResource(R.string.setup_connect)) }
    }
}
