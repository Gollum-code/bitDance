package com.example.demo.membership;

import com.example.demo.auth.JwtPrincipal;
import com.example.demo.auth.dto.UserDto;
import com.example.demo.auth.service.AuthService;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/membership")
public class MembershipController {

    private final MembershipService membershipService;
    private final AuthService authService;

    public MembershipController(MembershipService membershipService, AuthService authService) {
        this.membershipService = membershipService;
        this.authService = authService;
    }

    /**
     * 演示开通会员（无支付）。生产环境请接入支付后再调用开通逻辑。
     */
    @PostMapping("/upgrade-demo")
    public UserDto upgradeDemo(@AuthenticationPrincipal JwtPrincipal principal) {
        membershipService.upgradeToMember(principal.userId());
        return authService.me(principal.userId());
    }
}
