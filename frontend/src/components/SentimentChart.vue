<script setup lang="ts">
import { PieChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { SentimentItem } from '../types'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])
const props = defineProps<{ items: SentimentItem[] }>()
const labels: Record<string, string> = {
  positive: 'Positif',
  negative: 'Négatif',
  neutral: 'Neutre',
}
const colors: Record<string, string> = {
  positive: '#26d7a0',
  negative: '#ff6b82',
  neutral: '#f4b65d',
}
const option = computed(() => ({
  color: props.items.map((item) => colors[item.label]),
  tooltip: { trigger: 'item', formatter: '{b}<br/><strong>{c}</strong> avis ({d}%)' },
  legend: {
    bottom: 0,
    textStyle: { color: '#8ea3bd', fontFamily: 'Inter, sans-serif' },
    itemWidth: 9,
    itemHeight: 9,
  },
  series: [
    {
      type: 'pie',
      radius: ['55%', '78%'],
      center: ['50%', '43%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#101d2d', borderWidth: 4, borderRadius: 8 },
      label: { show: false },
      data: props.items.map((item) => ({ value: item.total, name: labels[item.label] })),
    },
  ],
}))
</script>

<template><VChart class="chart" :option="option" autoresize /></template>
