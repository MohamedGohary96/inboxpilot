import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@vuepic/vue-datepicker/dist/main.css'
import './style.css'
import App from './App.vue'
import { applyTheme, getActiveThemeId } from './themes'

applyTheme(getActiveThemeId())

createApp(App).use(createPinia()).mount('#app')
