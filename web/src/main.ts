import '@fontsource/prata/latin-400.css';
import '@fontsource/josefin-sans/latin-400.css';
import '@fontsource/josefin-sans/latin-400-italic.css';
import '@fontsource/josefin-sans/latin-600.css';
import '@fontsource/josefin-sans/latin-700.css';
import '@fontsource/cutive-mono/latin-400.css';
import '@fontsource/jetbrains-mono/500.css';
import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';

const app = mount(App, { target: document.getElementById('app')! });

export default app;
