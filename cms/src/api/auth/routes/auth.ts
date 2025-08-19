export default {
  routes: [
    {
      method: 'POST',
      path: '/auth/callback',
      handler: 'auth.callback',
      config: {
        policies: [],
        middlewares: [],
        auth: false,
      },
    },
    {
      method: 'POST',
      path: '/auth/register',
      handler: 'auth.register',
      config: {
        policies: [],
        middlewares: [],
        auth: false,
      },
    },
  ],
};
