
<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView />
</template>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Inter, Arial, sans-serif;
}

.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, #0b172a, #153854);
}

.login-card {
  width: 100%;
  max-width: 430px;
  padding: 36px;
  border-radius: 18px;
  background: #ffffff;
  color: #1b2a3a;
  box-shadow: 0 20px 60px #00000038;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 36px;
}

.brand-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: #116c88;
  color: white;
  font-size: 27px;
  font-weight: 800;
}

.brand strong {
  display: block;
  font-size: 23px;
}

.brand small {
  color: #64748b;
  font-size: 12px;
}

h1 {
  margin-bottom: 8px;
  font-size: 27px;
}

.subtitle {
  margin-bottom: 28px;
  color: #64748b;
  line-height: 1.5;
}

form {
  display: flex;
  flex-direction: column;
}

label {
  margin-bottom: 8px;
  font-weight: 600;
  font-size: 14px;
}

input {
  width: 100%;
  padding: 13px;
  margin-bottom: 20px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 15px;
}

input:focus {
  outline: 2px solid #116c88;
  outline-offset: 1px;
}

button {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 8px;
  background: #116c88;
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.profile {
  padding: 16px;
  margin-bottom: 24px;
  border-radius: 8px;
  background: #f1f5f9;
  overflow-wrap: anywhere;
}

.error {
  color: #b91c1c;
  margin-bottom: 16px;
  font-size: 14px;
}

footer {
  margin-top: 32px;
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
}
</style>