package app.garminuebersicht

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.DirectionsRun
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Today
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import app.garminuebersicht.ui.AppTheme
import app.garminuebersicht.ui.AppViewModel
import app.garminuebersicht.ui.SettingsScreen
import app.garminuebersicht.ui.SleepScreen
import app.garminuebersicht.ui.TodayScreen
import app.garminuebersicht.ui.TrainingScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { AppTheme { App() } }
    }
}

private data class Tab(val title: String, val icon: ImageVector)

private val TABS = listOf(
    Tab("Heute", Icons.Filled.Today),
    Tab("Training", Icons.AutoMirrored.Filled.DirectionsRun),
    Tab("Schlaf", Icons.Filled.Bedtime),
    Tab("Einstellungen", Icons.Filled.Settings),
)
private const val SETTINGS = 3

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun App(vm: AppViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    var tab by rememberSaveable { mutableIntStateOf(if (vm.settings.configured) 0 else SETTINGS) }

    Surface(color = MaterialTheme.colorScheme.background) {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background,
            topBar = {
                TopAppBar(
                    title = { Text(if (tab == 0) "Garmin-Übersicht" else TABS[tab].title) },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                    actions = {
                        if (tab != SETTINGS && vm.settings.configured) {
                            val syncing = state.syncRequested || state.status?.syncing == true
                            IconButton(onClick = vm::syncNow, enabled = !syncing) {
                                if (syncing) CircularProgressIndicator(Modifier.padding(12.dp), strokeWidth = 2.dp)
                                else Icon(Icons.Filled.Sync, contentDescription = "Jetzt mit Garmin abgleichen")
                            }
                            IconButton(onClick = vm::refresh, enabled = !state.loading) {
                                Icon(Icons.Filled.Refresh, contentDescription = "Neu laden")
                            }
                        }
                    },
                )
            },
            bottomBar = {
                NavigationBar {
                    TABS.forEachIndexed { i, t ->
                        NavigationBarItem(selected = tab == i, onClick = { tab = i },
                            icon = { Icon(t.icon, contentDescription = null) }, label = { Text(t.title) })
                    }
                }
            },
        ) { padding ->
            Column(Modifier.padding(padding).fillMaxSize()) {
                if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.takeIf { tab != SETTINGS }?.let {
                    Text(it, color = MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.errorContainer).padding(16.dp, 8.dp))
                }
                Box(Modifier.fillMaxSize()) {
                    when (tab) {
                        0 -> TodayScreen(state)
                        1 -> TrainingScreen(state, vm::setDays)
                        2 -> SleepScreen(state, vm::setDays)
                        else -> SettingsScreen(vm) { tab = 0 }
                    }
                }
            }
        }
    }
}
