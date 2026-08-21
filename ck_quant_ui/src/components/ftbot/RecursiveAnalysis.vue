<script setup lang="ts">
import type { RecursiveAnalysisPayload, RecursiveResult } from '@/types';
import { useI18n } from 'vue-i18n';

const botStore = useBotStore();
const { t } = useI18n();

const running = ref(false);
const result = ref<RecursiveResult | null>(null);
const statusMessage = ref('');

async function startAnalysis(payload: RecursiveAnalysisPayload) {
  running.value = true;
  result.value = null;
  statusMessage.value = '';
  try {
    const { job_id: jobId } = await botStore.activeBot.startRecursiveAnalysis(payload);
    const status = await botStore.activeBot.pollBgJob(jobId, 'recursive_analysis');
    if (status.status === 'failed') {
      statusMessage.value = status.error || t('research.recursiveFailed');
      showAlert(statusMessage.value, 'error');
      return;
    }
    const analysis = await botStore.activeBot.getRecursiveAnalysisResult(jobId);
    if (analysis.status === 'ended') {
      result.value = analysis.result;
      statusMessage.value = analysis.status_msg;
    } else {
      statusMessage.value = analysis.status_msg || t('research.recursiveFailed');
      showAlert(statusMessage.value, 'error');
    }
  } catch (error) {
    console.error(error);
    showAlert(t('research.runRecursiveFailed'), 'error');
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <div class="px-1 mx-auto w-full max-w-4xl lg:max-w-7xl">
    <BackgroundJobTracking class="mb-4" />
    <DraggableContainer :header="t('research.recursiveAnalysis')" class="mx-1 p-4">
      <RecursiveAnalysisForm :running="running" @start="startAnalysis" />
    </DraggableContainer>
    <DraggableContainer v-if="result" :header="t('research.analysisResult')" class="mx-1 mt-4 p-4">
      <RecursiveAnalysisResults :result="result" />
    </DraggableContainer>
  </div>
</template>
