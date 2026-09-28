import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import GraphView from './views/GraphView.vue'
import PlanView from './views/PlanView.vue'
import QuizView from './views/QuizView.vue'
import DashboardView from './views/DashboardView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/graph/:docId?', component: GraphView },
    { path: '/plan/:planId?', component: PlanView },
    { path: '/quiz/:planId?', component: QuizView },
    { path: '/dashboard/:docId?', component: DashboardView },
  ],
})
