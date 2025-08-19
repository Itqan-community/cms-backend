export default ({ env }) => ({
  connection: {
    client: 'postgres',
    connection: {
      host: env('DATABASE_HOST', 'postgres'),
      port: env.int('DATABASE_PORT', 5432),
      database: env('DATABASE_NAME', 'itqan_cms'),
      user: env('DATABASE_USERNAME', 'cms_user'),
      password: env('DATABASE_PASSWORD', 'dev_password_123'),
      ssl: env.bool('DATABASE_SSL', false),
    },
    debug: false,
  },
});
