<script setup lang="ts"></script>

<template>
  <div
    title="CK Quant"
    class="ckq-mark mx-auto grid place-items-center text-white transition-all duration-300"
  >
    <svg class="h-full w-full" viewBox="0 0 100 100" aria-hidden="true">
      <text
        x="48"
        y="63"
        fill="currentColor"
        font-family="Inter, Arial, sans-serif"
        font-size="34"
        font-weight="850"
        letter-spacing="-2"
        text-anchor="middle"
      >
        CK
      </text>
    </svg>
    <span class="sr-only">CK</span>
  </div>
</template>

<style scoped>
.ckq-mark {
  aspect-ratio: 1;
  border-radius: 28%;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.32), transparent 42%),
    linear-gradient(145deg, #45b7ff, #0a84ff 48%, #6558ff);
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.58),
    0 8px 20px rgba(10, 132, 255, 0.26);
}
</style>
