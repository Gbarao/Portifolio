import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: [
        'src/core/**/*.ts',
        'src/path/**/*.ts',
        'src/marbles/**/*.ts',
        'src/camera/**/*.ts',
      ],
      reporter: ['text', 'html'],
      thresholds: {
        lines: 70,
        statements: 70,
        functions: 70,
        branches: 60,
      },
    },
  },
});
