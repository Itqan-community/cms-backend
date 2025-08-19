export default ({ env }) => ({
  // Configure upload provider for MinIO (S3-compatible)
  upload: {
    config: {
      provider: 'aws-s3',
      providerOptions: {
        accessKeyId: env('AWS_ACCESS_KEY_ID'),
        secretAccessKey: env('AWS_SECRET_ACCESS_KEY'),
        region: env('AWS_REGION'),
        bucket: env('AWS_BUCKET'),
        endpoint: env('AWS_ENDPOINT'),
        forcePathStyle: env.bool('AWS_S3_FORCE_PATH_STYLE', true),
      },
      actionOptions: {
        upload: {},
        uploadStream: {},
        delete: {},
      },
    },
  },

  // Configure i18n for English/Arabic support
  i18n: {
    enabled: true,
    config: {
      defaultLocale: 'en',
      locales: ['en', 'ar'],
    },
  },

  // Configure Meilisearch integration
  meilisearch: {
    enabled: true,
    config: {
      host: env('MEILI_HOST', 'http://meilisearch:7700'),
      apiKey: env('MEILI_MASTER_KEY'),
      indexPrefix: 'itqan_',
    },
  },

  // Users & Permissions configuration for Auth0 integration
  'users-permissions': {
    config: {
      register: {
        allowedFields: ['username', 'email', 'auth0_id'],
      },
      jwt: {
        expiresIn: '7d',
      },
    },
  },
});
