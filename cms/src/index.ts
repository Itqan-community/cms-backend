export default {
  /**
   * An asynchronous register function that runs before
   * your application is initialized.
   *
   * This gives you an opportunity to extend code.
   */
  register(/*{ strapi }*/) {},

  /**
   * An asynchronous bootstrap function that runs before
   * your application gets started.
   *
   * This gives you an opportunity to set up your data model,
   * run jobs, or perform some special logic.
   */
  async bootstrap({ strapi }) {
    // Initialize default roles if they don't exist
    const pluginStore = strapi.store({
      environment: '',
      type: 'plugin',
      name: 'users-permissions',
    });

    const settings = await pluginStore.get({
      key: 'advanced',
    });

    if (!settings) {
      const value = {
        unique_email: true,
        allow_register: true,
        email_confirmation: false,
        email_reset_password: 'http://localhost:3000/reset-password',
        email_confirmation_redirection: 'http://localhost:3000/dashboard',
        default_role: 'authenticated',
      };

      await pluginStore.set({
        key: 'advanced',
        value,
      });
    }

    strapi.log.info('🚀 Itqan CMS Strapi backend initialized');
  },
};
