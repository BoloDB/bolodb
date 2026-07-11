// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
  namespace App {
    // interface Error {}
    // interface Locals {}
    // interface PageData {}
    // interface PageState {}
    // interface Platform {}
  }

  interface Window {
    __GOOGLE_CLIENT_ID__?: string;
  }

  namespace google.accounts.id {
    interface CredentialResponse {
      credential: string;
      select_by?: string;
    }
    interface IdConfiguration {
      client_id: string;
      callback: (response: CredentialResponse) => void;
      auto_select?: boolean;
      cancel_on_tap_outside?: boolean;
      context?: "signin" | "signup" | "use";
    }
    function initialize(config: IdConfiguration): void;
    function renderButton(
      parent: HTMLElement,
      options: {
        theme?: string;
        size?: string;
        width?: number;
        shape?: string;
        logo_alignment?: string;
      },
    ): void;
    function disableAutoSelect(): void;
    function storeCredential(credential: string, callback?: () => void): void;
    function cancel(): void;
    function prompt(momentListener?: (moment: string) => void): void;
  }

  const google: {
    accounts: {
      id: typeof google.accounts.id;
    };
  };
}

export {};
