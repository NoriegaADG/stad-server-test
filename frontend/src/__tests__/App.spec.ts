import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import App from '../App.vue'

describe('App', () => {
  it('renderiza el contenedor de rutas', () => {
    const wrapper = shallowMount(App)

    expect(wrapper.find('router-view-stub').exists()).toBe(true)
  })
})
