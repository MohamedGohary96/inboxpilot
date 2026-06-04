import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@vuepic/vue-datepicker/dist/main.css'
import './style.css'
import App from './App.vue'

createApp(App).use(createPinia()).mount('#app')
