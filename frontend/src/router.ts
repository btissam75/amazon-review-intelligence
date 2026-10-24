import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
    { path: '/products', name: 'products', component: () => import('./views/ProductsView.vue') },
    {
      path: '/recommendations',
      name: 'recommendations',
      component: () => import('./views/RecommendationsView.vue'),
    },
    { path: '/nlp', name: 'nlp', component: () => import('./views/NlpLabView.vue') },
    { path: '/system', name: 'system', component: () => import('./views/SystemView.vue') },
  ],
})
