import { factories } from '@strapi/strapi';
import axios from 'axios';

export default factories.createCoreController('api::auth.auth', ({ strapi }) => ({
  async callback(ctx) {
    try {
      const { accessToken, idToken } = ctx.request.body;

      if (!accessToken) {
        return ctx.badRequest('Access token is required');
      }

      // Verify the token with Auth0
      const auth0Response = await axios.get(`https://${process.env.AUTH0_DOMAIN}/userinfo`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      const auth0User = auth0Response.data;
      
      // Check if user already exists in Strapi
      let user = await strapi.db.query('plugin::users-permissions.user').findOne({
        where: { auth0_id: auth0User.sub },
      });

      if (!user) {
        // Create new user in Strapi
        const defaultRole = await strapi.db.query('plugin::users-permissions.role').findOne({
          where: { type: 'authenticated' },
        });

        user = await strapi.db.query('plugin::users-permissions.user').create({
          data: {
            username: auth0User.nickname || auth0User.email.split('@')[0],
            email: auth0User.email,
            auth0_id: auth0User.sub,
            confirmed: auth0User.email_verified || false,
            role: defaultRole.id,
            provider: 'auth0',
          },
        });

        strapi.log.info(`New user created: ${user.email} (Auth0: ${auth0User.sub})`);
      }

      // Generate Strapi JWT
      const jwt = strapi.plugins['users-permissions'].services.jwt.issue({
        id: user.id,
        email: user.email,
      });

      ctx.send({
        jwt,
        user: {
          id: user.id,
          username: user.username,
          email: user.email,
          confirmed: user.confirmed,
        },
      });
    } catch (error) {
      strapi.log.error('Auth callback error:', error);
      ctx.internalServerError('Authentication failed');
    }
  },

  async register(ctx) {
    try {
      const { email, auth0_id, username } = ctx.request.body;

      if (!email || !auth0_id) {
        return ctx.badRequest('Email and Auth0 ID are required');
      }

      // Check if user already exists
      const existingUser = await strapi.db.query('plugin::users-permissions.user').findOne({
        where: { 
          $or: [
            { email },
            { auth0_id }
          ]
        },
      });

      if (existingUser) {
        return ctx.conflict('User already exists');
      }

      // Get default role (Viewer)
      const defaultRole = await strapi.db.query('plugin::users-permissions.role').findOne({
        where: { type: 'authenticated' },
      });

      // Create new user
      const user = await strapi.db.query('plugin::users-permissions.user').create({
        data: {
          username: username || email.split('@')[0],
          email,
          auth0_id,
          confirmed: false, // Will be confirmed via Auth0 email verification
          role: defaultRole.id,
          provider: 'auth0',
        },
      });

      ctx.send({
        user: {
          id: user.id,
          username: user.username,
          email: user.email,
          auth0_id: user.auth0_id,
        },
      });
    } catch (error) {
      strapi.log.error('Registration error:', error);
      ctx.internalServerError('Registration failed');
    }
  },
}));
