import { createApp } from "vue";

import App from "@/App.vue";
import { bootstrapToken } from "@/api/client";
import "@/style.css";

bootstrapToken();
createApp(App).mount("#app");
