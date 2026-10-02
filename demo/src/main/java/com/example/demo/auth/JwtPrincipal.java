package com.example.demo.auth;

import java.security.Principal;

public record JwtPrincipal(Long userId, String username) implements Principal {

    @Override
    public String getName() {
        return username;
    }
}
