import { mount } from 'svelte';
import MiniWidget from './views/MiniWidget.svelte';

const app = mount(MiniWidget, { target: document.getElementById('mini')! });

export default app;
